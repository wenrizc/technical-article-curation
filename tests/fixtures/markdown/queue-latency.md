# How We Debugged Queue Latency

We observed p99 latency growth in a production queue.

The team compared batching, backpressure, and partitioning tradeoffs.

```text
queue_depth_bucket{le="100"}
```

