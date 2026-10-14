# Shared in-memory cache for uploaded/ingested products keyed by session_upload_id
# Avoids database storage until a run is officially built
_UPLOAD_CACHE = {}
