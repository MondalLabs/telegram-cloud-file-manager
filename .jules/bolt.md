## 2024-05-18 - Concurrent MongoDB Queries for Navigation
**Learning:** In Pyrogram+Beanie async setups, directory navigation reads (fetching folders and files separately) can double network latency if executed sequentially.
**Action:** Use `asyncio.gather` to execute independent database read operations concurrently.

## 2026-05-19 - MongoDB Blocking Sort in Directory Listing
**Learning:** In MongoDB, querying by one field (`folder_id` or `parent_id`) and sorting by another (`name`) without a covering compound index forces an in-memory blocking sort. This is a severe bottleneck for large directories as MongoDB limits in-memory sorts to 32MB.
**Action:** Always create compound indexes `[("filter_field", ASCENDING), ("sort_field", ASCENDING)]` when a collection is regularly queried and sorted, such as directory listings.
