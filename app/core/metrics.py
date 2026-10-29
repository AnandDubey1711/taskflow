from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP requests by method, route template and status code",
    ["method", "route", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration by method and route template",
    ["method", "route"],
)

TASK_SEARCH_CACHE_LOOKUPS_TOTAL = Counter(
    "task_search_cache_lookups_total",
    "GET /tasks cache lookups by result",
    ["result"],
)
