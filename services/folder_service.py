"""
services/folder_service.py
─────────────────────────────────────────────────────────────────────────────
All business logic for the folder hierarchy.

Key design choices:
  • get_children uses a single indexed query — O(1) for directory browsing.
  • delete_folder_tree uses $graphLookup (Safeguard #2) to collect ALL
    descendant IDs in one query, then bulk-deletes with 2 operations total,
    regardless of tree depth.
  • bson.ObjectId() cast is used when injecting IDs into raw pipelines
    (Safeguard #5) to prevent silent match failures.
"""

from __future__ import annotations

from typing import Optional

from beanie import PydanticObjectId
from bson import ObjectId

from models.folder import Folder
from models.file import File


async def get_children(parent_id: Optional[PydanticObjectId]) -> list[Folder]:
    """Return all immediate child folders of the given parent (or root if None), sorted by name."""
    return await Folder.find(Folder.parent_id == parent_id).sort(+Folder.name).to_list()


async def count_children(parent_id: Optional[PydanticObjectId]) -> int:
    """Return the total count of immediate child folders of the given parent."""
    return await Folder.find(Folder.parent_id == parent_id).count()


async def get_children_paginated(
    parent_id: Optional[PydanticObjectId], skip: int, limit: int
) -> list[Folder]:
    """Return a paginated slice of immediate child folders of the given parent, sorted by name."""
    return (
        await Folder.find(Folder.parent_id == parent_id)
        .sort(+Folder.name)
        .skip(skip)
        .limit(limit)
        .to_list()
    )


async def get_folder(folder_id: PydanticObjectId) -> Optional[Folder]:
    """Fetch a single folder by its _id."""
    return await Folder.get(folder_id)


async def create_folder(
    name: str,
    parent_id: Optional[PydanticObjectId],
    created_by: int,
) -> Folder:
    """
    Insert a new folder.
    Raises ValueError if a sibling with the same name already exists
    (the unique index would reject it anyway, but we raise early with a
    human-readable message so the handler can reply gracefully).
    """
    existing = await Folder.find_one(
        Folder.name == name,
        Folder.parent_id == parent_id,
    )
    if existing:
        raise ValueError(f"A folder named '{name}' already exists here.")

    folder = Folder(name=name, parent_id=parent_id, created_by=created_by)
    await folder.insert()
    return folder


async def rename_folder(folder_id: PydanticObjectId, new_name: str) -> Optional[Folder]:
    """Rename a folder. Returns the updated document or None if not found."""
    folder = await Folder.get(folder_id)
    if folder is None:
        return None

    # Check sibling uniqueness before updating
    sibling = await Folder.find_one(
        Folder.name == new_name,
        Folder.parent_id == folder.parent_id,
        Folder.id != folder_id,
    )
    if sibling:
        raise ValueError(f"A folder named '{new_name}' already exists here.")

    folder.name = new_name
    await folder.save()
    return folder


async def delete_folder_tree(folder_id: PydanticObjectId) -> dict:
    """
    Delete a folder and ALL its descendants (sub-folders and their files).

    Strategy (Safeguard #2):
      1. $graphLookup collects every descendant _id in ONE aggregation query.
      2. delete_many on folders collection.
      3. delete_many on files collection.
      Total: 3 MongoDB round-trips regardless of tree depth.

    Safeguard #5: bson.ObjectId() cast ensures the $match stage works correctly
    with Beanie's PydanticObjectId wrapper.
    """
    raw_id = ObjectId(str(folder_id))  # Safeguard #5: explicit cast

    pipeline = [
        {"$match": {"_id": raw_id}},
        {
            "$graphLookup": {
                "from": "folders",
                "startWith": "$_id",
                "connectFromField": "_id",
                "connectToField": "parent_id",
                "as": "descendants",
            }
        },
        {
            "$project": {
                "descendant_ids": {
                    "$map": {
                        "input": "$descendants",
                        "as": "d",
                        "in": "$$d._id",
                    }
                }
            }
        },
    ]

    results = await Folder.aggregate(pipeline).to_list(1)
    descendant_ids: list[ObjectId] = results[0]["descendant_ids"] if results else []

    # All folder IDs to delete (target + all descendants)
    all_folder_ids = [raw_id] + descendant_ids

    # Bulk delete files in those folders
    file_result = await File.find(
        {"folder_id": {"$in": all_folder_ids}}
    ).delete()

    # Bulk delete the folders themselves
    folder_result = await Folder.find(
        {"_id": {"$in": all_folder_ids}}
    ).delete()

    return {
        "folders_deleted": folder_result.deleted_count if folder_result else 0,
        "files_deleted": file_result.deleted_count if file_result else 0,
    }


async def get_breadcrumbs(folder_id: PydanticObjectId) -> list[Folder]:
    """
    Return the ancestor chain from root → immediate parent of folder_id.
    Result is ordered root-first (for breadcrumb display).
    Uses an iterative walk — breadcrumbs are typically shallow (3–5 levels).
    """
    breadcrumbs: list[Folder] = []
    current_id: Optional[PydanticObjectId] = folder_id

    while current_id is not None:
        folder = await Folder.get(current_id)
        if folder is None:
            break
        breadcrumbs.append(folder)
        current_id = folder.parent_id

    breadcrumbs.reverse()  # root → ... → current
    return breadcrumbs


async def move_folder(
    folder_id: PydanticObjectId,
    target_parent_id: Optional[PydanticObjectId]
) -> Folder:
    """
    Move a folder to a new parent folder.
    Prevents cycle/self-nesting and handles name collisions.
    """
    folder = await Folder.get(folder_id)
    if not folder:
        raise ValueError("Folder not found.")

    # 1. Self-nesting prevention: check if target_parent_id is folder_id or a child of folder_id
    curr_id = target_parent_id
    while curr_id is not None:
        if curr_id == folder_id:
            raise ValueError("Cannot move a folder into itself or one of its subfolders.")
        parent_folder = await Folder.get(curr_id)
        if not parent_folder:
            break
        curr_id = parent_folder.parent_id

    # 2. Check name collision in target folder
    name = folder.name
    suffix = ""
    counter = 1
    base_name = name
    while True:
        existing = await Folder.find_one(
            Folder.name == f"{base_name}{suffix}",
            Folder.parent_id == target_parent_id,
            Folder.id != folder_id
        )
        if not existing:
            name = f"{base_name}{suffix}"
            break
        suffix = f"_{counter}"
        counter += 1

    folder.parent_id = target_parent_id
    folder.name = name
    await folder.save()
    return folder


async def copy_folder(
    folder_id: PydanticObjectId,
    target_parent_id: Optional[PydanticObjectId],
    created_by: int
) -> Folder:
    """
    Recursively copies a folder, its subfolders, and all contained files.
    Resolves name conflicts in the destination folder.
    """
    src = await Folder.get(folder_id)
    if not src:
        raise ValueError("Source folder not found.")

    # 1. Resolve name conflict at target parent
    name = src.name
    suffix = ""
    counter = 1
    base_name = name
    while True:
        existing = await Folder.find_one(
            Folder.name == f"{base_name}{suffix}",
            Folder.parent_id == target_parent_id
        )
        if not existing:
            name = f"{base_name}{suffix}"
            break
        suffix = f"_{counter}"
        counter += 1

    # 2. Insert new duplicated folder
    new_folder = Folder(name=name, parent_id=target_parent_id, created_by=created_by)
    await new_folder.insert()

    # 3. Recursively copy subfolders
    child_folders = await Folder.find(Folder.parent_id == folder_id).to_list()
    for child in child_folders:
        await copy_folder(child.id, new_folder.id, created_by)

    # 4. Copy all files in the source folder
    child_files = await File.find(File.folder_id == folder_id).to_list()
    for f in child_files:
        new_file = File(
            name=f.name,
            file_id=f.file_id,
            file_type=f.file_type,
            folder_id=new_folder.id,
            dump_message_id=f.dump_message_id,
            file_size=f.file_size,
            duration=f.duration,
            width=f.width,
            height=f.height,
            mime_type=f.mime_type,
            uploaded_by=created_by
        )
        await new_file.insert()

    return new_folder


async def get_folder_size(folder_id: PydanticObjectId) -> dict:
    """
    Calculate the total size and count of files/folders recursively inside a folder.
    """
    raw_id = ObjectId(str(folder_id))
    pipeline = [
        {"$match": {"_id": raw_id}},
        {
            "$graphLookup": {
                "from": "folders",
                "startWith": "$_id",
                "connectFromField": "_id",
                "connectToField": "parent_id",
                "as": "descendants",
            }
        },
        {
            "$project": {
                "descendant_ids": {
                    "$map": {
                        "input": "$descendants",
                        "as": "d",
                        "in": "$$d._id",
                    }
                }
            }
        },
    ]

    results = await Folder.aggregate(pipeline).to_list(1)
    descendant_ids = results[0]["descendant_ids"] if results else []
    all_folder_ids = [raw_id] + descendant_ids

    # Query sum of file_size in all_folder_ids
    file_pipeline = [
        {"$match": {"folder_id": {"$in": all_folder_ids}}},
        {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}, "total_files": {"$sum": 1}}}
    ]
    file_stats = await File.aggregate(file_pipeline).to_list(1)
    total_size = file_stats[0]["total_size"] if file_stats else 0
    total_files = file_stats[0]["total_files"] if file_stats else 0

    return {
        "size": total_size,
        "files_count": total_files,
        "folders_count": len(descendant_ids)
    }
