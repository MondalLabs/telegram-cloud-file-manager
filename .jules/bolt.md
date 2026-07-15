## 2024-05-18 - Concurrent MongoDB Queries for Navigation
**Learning:** In Pyrogram+Beanie async setups, directory navigation reads (fetching folders and files separately) can double network latency if executed sequentially.
**Action:** Use `asyncio.gather` to execute independent database read operations concurrently.

## 2026-05-19 - MongoDB Blocking Sort in Directory Listing
**Learning:** In MongoDB, querying by one field (`folder_id` or `parent_id`) and sorting by another (`name`) without a covering compound index forces an in-memory blocking sort. This is a severe bottleneck for large directories as MongoDB limits in-memory sorts to 32MB.
**Action:** Always create compound indexes `[("filter_field", ASCENDING), ("sort_field", ASCENDING)]` when a collection is regularly queried and sorted, such as directory listings.

## 2024-06-25 - MongoDB Pagination for Directory Listings
**Learning:** Fetching an entire collection (all files and folders in a directory) into memory just to display a paginated slice is a severe O(N) memory and latency bottleneck, particularly for large directories. Relying on an in-memory `paginate` utility for database records defeats the purpose of database query optimizations like skip and limit.
**Action:** When displaying paginated results from MongoDB, always compute pagination boundaries based on `.count()` queries and use `.skip().limit()` at the DB level to retrieve only the requested slice.
## 2024-05-19 - MongoDB Pagination for Approved Users
**Learning:** Fetching an entire collection of approved users into memory to display a paginated slice is a severe O(N) memory and latency bottleneck, identical to the directory listings issue previously identified.
**Action:** Always compute pagination boundaries based on `.count()` queries and use `.skip().limit()` at the DB level to retrieve only the requested slice for user listings as well.

## 2024-05-20 - N+1 Query Storms in Recursive Permission Checks
**Learning:** Evaluating hierarchical permissions (walking up ancestor paths in the DB) inside a concurrent list comprehension across directory contents causes a severe N+1 query storm. Even with concurrent execution, fetching the path for every single file/folder overwhelms the database.
**Action:** Always provide an early return fast-path for the default permission case (e.g., when the user has no specific allow/block rules configured) to entirely skip the DB path-walking loop.
