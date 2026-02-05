# Scale AI System Design — Revised Talking Script (v2)

## Changes from v1
- Caching is now CONDITIONAL, not the primary optimization
- Parallelism and smart batching are the headline optimizations
- Added detailed parallelism explanation
- Added concrete cost savings with dollar amounts
- Every term explained without acronyms

---

## Opening (First 5 Minutes)

### What to Say

> "Great, thanks for walking me through the problem. Before I start designing, let me ask a few clarifying questions."

**Ask these:**

> "For the sub-1-second latency requirement — is that end-to-end including both embedding generation and classification? Or just one of those steps?"

> "For 1,000 assets per second — is that sustained throughput or a peak burst?"

> "How often do models get updated? That affects how I think about storing and organizing the embeddings."

> "For the stored embeddings and results — do you need real-time query access for debugging, or is it okay if retrieval takes a few seconds?"

---

## The Key Insight — Say This First (2 Minutes)

### What to Say

> "Before I draw anything, let me highlight the critical constraint in this problem."

> "Black Box 1 accepts 200 files per call. Black Box 2 accepts 2,000 embeddings per call. That's a 10-to-1 ratio. To process 2,000 files, I need **10 calls to Black Box 1** but only **1 call to Black Box 2**."

> "That tells me three things:"
>
> "First, **Black Box 1 is the bottleneck**. It's where most of the time and cost goes. My architecture should focus on making Black Box 1 calls as efficient as possible."
>
> "Second, the pattern here is **fan-out then fan-in** — I split files across many parallel Black Box 1 calls, then combine all the embeddings into one Black Box 2 call."
>
> "Third, my optimization priority should be: **parallelism first, smart batching second, then everything else**. These two optimizations work regardless of whether files are unique or repeated."

---

## The Application Programming Interface Design (8 Minutes)

### What to Say

> "I'm going to create two separate endpoints — one for customers who need speed, one for customers who need volume."

### Real-Time Endpoint (Synchronous)

> "The first endpoint is for real-time classification. The customer sends files and waits for the result — like ordering at a counter and waiting for your food."

**Address:** POST /v1/classify/realtime

> "The customer sends a request with up to 50 files. Our system processes them immediately and sends back classification results in the same connection. The customer's application blocks — meaning it pauses and waits — until we respond."

> "The request looks something like this:"

```
Customer sends:
{
  "files": ["file_ref_1", "file_ref_2", ...up to 50],
  "options": {
    "confidence_threshold": 0.8
  }
}

System responds immediately:
{
  "request_id": "abc-123",
  "results": [
    {
      "file_id": "file_ref_1",
      "classifications": {
        "spam": 0.93,
        "safe_content": 0.85,
        "violence": 0.01
      }
    },
    ... one result per file
  ],
  "processing_time_ms": 620
}
```

### Batch Endpoint (Asynchronous)

> "The second endpoint is for customers with thousands of files who care about throughput and cost, not speed. This is like dropping off dry cleaning — you leave the work and pick it up later."

**Address:** POST /v1/classify/batch

> "The customer sends a large batch. We immediately give them a job identifier — a receipt number. They check back later for results."

```
Customer sends:
{
  "files": ["file_1", "file_2", ... up to 10,000+],
  "webhook_url": "https://customer.com/callback"  (optional notification address)
}

System responds immediately:
{
  "job_id": "job-456",
  "status": "accepted",
  "total_files": 5000,
  "check_status_at": "/v1/jobs/job-456"
}
```

> "The customer can then check progress:"

```
GET /v1/jobs/job-456

{
  "job_id": "job-456",
  "status": "processing",
  "total_files": 5000,
  "processed_files": 3200,
  "progress": 0.64
}
```

> "When the job completes, we either notify them at their callback address or they poll until the status says 'completed.'"

### Why Two Endpoints Instead of One

> "I chose separate endpoints because each path has fundamentally different behavior. The real-time path never waits — it processes whatever you send immediately, even if the batch isn't full. The batch path deliberately waits to accumulate full batches of 200 because that's more cost-efficient. Putting both behind one endpoint with a mode flag would make the code harder to reason about and optimize."

### Supporting Endpoints

> "We also need:"
>
> - **GET /v1/jobs/{job_id}** — Check job status and progress
> - **GET /v1/jobs/{job_id}/results** — Download completed results
> - **GET /v1/results/{request_id}** — Look up past real-time results
> - **GET /v1/embeddings/{file_hash}** — Retrieve stored embeddings for debugging

---

## System Architecture (15 Minutes)

> "Let me walk through the architecture from top to bottom."

---

### Layer 1: The Gateway

> "Every request first hits the gateway. This is the front door and security desk for the entire system. It does three things:"

> "**One — Identity verification.** The customer includes a secret key with every request. The gateway checks that this key is valid and identifies which customer it belongs to. This lets us track usage per customer and bill accordingly."

> "**Two — Rate limiting.** Each customer has a cap on how many requests they can send per minute. If they exceed it, the gateway returns an error that says 'you've exceeded your limit, try again in 30 seconds.' This is critical because it prevents any single customer from using up all the system's capacity and degrading service for everyone else."

> "**Three — Routing.** Based on which address the customer called — /realtime or /batch — the gateway sends the request to the appropriate service. This is simple path-based routing: different addresses go to different services."

---

### Layer 2: Two Processing Paths

#### Real-Time Service (Left Side of Diagram)

> "This service handles the fast path. When a request arrives, it processes immediately. No queuing, no waiting. It calls the orchestration layer — which I'll walk through in detail — and returns the results directly to the customer."

> "The key design choice: we **never** wait to accumulate a bigger batch. If the customer sends 5 files, we process 5 files. We're optimizing for latency, not for efficient use of Black Box 1. We'll address efficiency on the batch path."

#### Batch Ingestion Service (Right Side of Diagram)

> "This service handles the cost-efficient path. When a large request arrives, it does two things:"

> "**First**, it writes a job record to our PostgreSQL database. This is a permanent record: 'Customer X submitted 5,000 files at 2pm, status: pending.' This record is the source of truth. If anything else crashes, we can always reconstruct what work needs to be done from this record."

> "**Second**, it breaks the request into chunks of 200 files — matching Black Box 1's limit — and places each chunk as a task in a queue."

---

### Layer 2.5: The Task Queue (Batch Path Only)

> "A task queue is a to-do list that worker processes pull from. Think of it like a ticket dispenser at a deli counter — customers take a number, workers call the next number when they're ready."

> "If a customer sends 5,000 files, the batch service creates 25 tasks (5,000 divided by 200) and drops them into the queue. Worker processes — which are copies of the processing code running on separate machines — each pull one task, process it, and come back for the next one."

**Why a queue? Say this:**

> "The queue serves three purposes:"
>
> "**Traffic absorption.** If 10 customers each submit 10,000 files at once, that's 100,000 files hitting our system simultaneously. Without a queue, we'd need enough machines to handle that spike — and most of the time those machines would sit idle. With a queue, the work piles up and workers process it at a steady, efficient pace."
>
> "**Crash recovery.** When a worker picks up a task, the task becomes invisible to other workers but isn't deleted yet. If the worker finishes, it deletes the task. If the worker crashes, the task reappears in the queue after a timeout — say 5 minutes — and another worker picks it up. No work is lost."
>
> "**Cost control.** We can run exactly the number of workers we can afford. During quiet periods, we run 3 workers. During sustained high load, we spin up 15. The queue decouples 'how fast work arrives' from 'how fast we process it.'"

---

### Layer 3: The Orchestration Layer (The Core)

> "This is the heart of the system. Both the real-time service and the batch workers call this same orchestration logic. This is where all the optimizations live."

---

#### OPTIMIZATION #1: Parallelism (Explain in Detail)

> "This is the single most impactful optimization, so let me walk through it carefully."

> "Let's say we need to generate embeddings for 1,000 files. Black Box 1 accepts 200 files per call, so we need 5 calls. The question is: do we make those 5 calls one after another, or all at the same time?"

**Draw this on the whiteboard:**

> "**Sequential approach — one after another:**"

```
Time:   0ms    400ms    800ms    1200ms   1600ms   2000ms
        |───────|────────|────────|────────|────────|
        BB1      BB1      BB1      BB1      BB1
        call 1   call 2   call 3   call 4   call 5
        
Total time for embedding: 2,000 milliseconds
```

> "Each call takes about 400 milliseconds. Five calls back to back takes 2,000 milliseconds. That's already over our 1-second budget before we even get to classification."

> "**Parallel approach — all at the same time:**"

```
Time:   0ms                                 400ms
        |───────────────────────────────────|
        BB1 call 1 (files 1-200)            |
        BB1 call 2 (files 201-400)          |
        BB1 call 3 (files 401-600)          |  All finish at ~400ms
        BB1 call 4 (files 601-800)          |
        BB1 call 5 (files 801-1000)         |
        
Total time for embedding: 400 milliseconds
```

> "All 5 calls start at the same time. Each one takes about 400 milliseconds. Since they're running simultaneously, the total time is just 400 milliseconds — the same as a single call. We went from 2,000 milliseconds to 400 milliseconds. That's an **80% reduction in latency**."

**How parallelism actually works — explain simply:**

> "Here's what's happening under the hood. Our worker is not a single thread doing one thing at a time. It uses what's called **asynchronous input/output**. When we send a request to Black Box 1, our worker doesn't sit and wait — it says 'I'll check back when the response arrives' and immediately sends the next request."

> "It's like a waiter at a restaurant. A good waiter doesn't stand at one table waiting for the kitchen to cook that table's order. They take table 1's order, send it to the kitchen, then walk to table 2, take their order, send it to the kitchen, and so on. All the orders are being cooked at the same time in the kitchen."

> "In our case, the 'kitchen' is the Black Box 1 service — it has the capacity to handle multiple requests at once (the problem statement says it can scale upward). Our worker is the 'waiter' — it fires off all the requests and collects the results as they come back."

**The code pattern:**

> "In code, this looks like:"

```python
# Split files into chunks of 200
chunks = split_into_groups(files, group_size=200)

# Fire ALL calls at the same time
# asyncio.gather() starts all calls simultaneously and waits for all to finish
all_embeddings = await asyncio.gather(
    black_box_1.embed(chunks[0]),  # starts immediately
    black_box_1.embed(chunks[1]),  # starts immediately
    black_box_1.embed(chunks[2]),  # starts immediately
    black_box_1.embed(chunks[3]),  # starts immediately
    black_box_1.embed(chunks[4]),  # starts immediately
)
# All 5 return after ~400ms total, not 2000ms
```

> "The key function here is asyncio.gather() — it takes a list of operations, starts all of them at the same time, and waits until every one has finished. The total wait time equals the slowest individual call, not the sum of all calls."

**Why this is the #1 optimization:**

> "This works for **every single request** — it doesn't matter whether the files are unique or repeated. Even if caching were somehow 100% effective, parallelism still matters because the cache lookups themselves benefit from being batched. And in the realistic case where most files are unique, parallelism is the difference between meeting the 1-second target and not."

---

#### OPTIMIZATION #2: Smart Batching (Always Fill to 200)

> "The second optimization: always fill Black Box 1 calls to the maximum of 200 files."

> "This matters because the cost of calling Black Box 1 is likely per-call, not per-file. Or at minimum, there's overhead per call — connection setup, network round trips, model loading. Sending 200 files in one call is much cheaper than sending 50 files in four separate calls, even though the total file count is the same."

> "For the real-time path, we can't always fill to 200 — if the customer sends 30 files, we send 30. We won't wait for more. But we make sure we don't accidentally split into smaller batches."

> "For the batch path, we absolutely fill to 200 every time. The batch service chunks files into groups of exactly 200 before putting them in the queue. Workers always process full batches."

**The math:**

> "10 million files per day:"
>
> "If average batch size is 50: that's 200,000 Black Box 1 calls"
> "If average batch size is 200: that's 50,000 Black Box 1 calls"
>
> "Same number of files, 75% fewer calls. At $0.01 per call, that's $1,500 per day saved — over $500,000 per year."

---

#### OPTIMIZATION #3: Asynchronous Storage Writes

> "The problem statement asks us to store embeddings and results for debugging and analysis. We absolutely should — but we should not make the customer wait for those writes."

> "When the classification results come back from Black Box 2, we immediately return them to the customer. In the background — after the response is already sent — we write the results and embeddings to our database and file storage."

> "This is called a 'fire and forget' pattern. We start the write operation but don't wait for it to complete before responding."

```python
# Get results from Black Box 2
results = await black_box_2.classify(all_embeddings)

# Start the save, but DON'T wait for it
# asyncio.create_task() starts the work in the background
asyncio.create_task(save_to_database(results))
asyncio.create_task(save_embeddings_to_storage(all_embeddings))

# Return to the customer immediately — don't block on the saves
return results
```

> "If the database write fails, we log the failure and retry later. The customer doesn't experience any delay either way."

> "This saves about 50 to 100 milliseconds per request. That might not sound like much, but on the real-time path where our budget is under 1,000 milliseconds, saving 100 milliseconds is significant — it's the difference between a comfortable margin and cutting it close."

---

#### OPTIMIZATION #4 (Conditional): Embedding Cache

> "Now, about caching. I want to be honest about when this helps and when it doesn't."

> "Caching embeddings means: before calling Black Box 1, check if we've already generated an embedding for this exact file. If we have, skip Black Box 1 and use the stored embedding."

> "This is extremely valuable in specific use cases. **Content moderation** is the best example — the same spam image or viral meme gets flagged thousands of times by different users. In that scenario, the cache hit rate could be 80% or higher, and the savings are enormous."

> "But for **unique content classification** — where every file is different, like classifying a dataset of unique product images or processing original documents — the cache hit rate will be near zero. Every file is a miss, and the cache is just wasted memory."

> "So my approach is: **build the cache layer, but make it conditional**. Track the hit rate in production. If it's above 10%, the cache is paying for itself — scale it up. If it's below 5%, it's not helping — scale it down or disable it. This is a data-driven decision, not an assumption."

> "Critically, the three optimizations above — parallelism, batch filling, and async writes — deliver savings **regardless** of cache performance. They're the foundation. Caching is a bonus that may or may not pay off."

---

### Layer 4: Storage

> "The problem statement specifically requires us to store model results and embeddings for debugging and analysis. Here's how I organize the storage:"

#### PostgreSQL — The Permanent Record

> "PostgreSQL is our relational database — the one source of truth. It stores:"

> "**Classification results** — every label and confidence score we've returned, linked to which file produced it, which model version was used, and which customer requested it. This lets us run analytical queries like 'show me all files classified as spam with confidence above 90% in the last week.'"

> "**Job records** — for the batch path, the status, progress, timing, and customer information for every job."

> "**Embedding metadata** — not the actual embedding vectors (those are large and go in file storage), but information about where each embedding is stored, when it was created, which model version produced it, and when it was last accessed."

> "Why PostgreSQL? It's reliable, supports complex queries for analysis, and has a flexible data type called JSONB that lets us store the classification dictionaries without needing to define every possible label as a column."

#### Redis — Fast Temporary Storage

> "Redis keeps data in the computer's working memory, which makes it extremely fast — under 1 millisecond per lookup. We use it for:"

> "**Rate limit counters** — tracking how many requests each customer has made in the current time window."

> "**Task queue** — if we use Redis for the batch path queue, tasks live here temporarily until workers consume them."

> "**Embedding cache** — if enabled, this is where cached embeddings live for fast retrieval."

> "The trade-off: Redis is fast but data is lost if it crashes. That's fine for rate limits (they reset anyway) and cache (we can regenerate), which is why permanent records go in PostgreSQL."

#### Amazon S3 — Cheap Bulk Storage

> "S3 is like a giant warehouse. It's inexpensive, virtually unlimited, and Amazon guarantees durability. We store:"

> "**Embedding vectors** — these are large (several kilobytes each) and we need them for debugging but don't need millisecond access. S3 retrieval takes 50-100 milliseconds, which is fine for debugging purposes."

> "**Original files** — if we need to re-process or investigate an issue."

> "**Archived results** — older classification results that we don't query frequently."

---

## How This Saves the Company Money (5 Minutes)

### What to Say

> "Let me walk through the concrete cost savings of this design. I'll assume Scale AI processes 10 million files per day and Black Box 1 costs about $0.01 per call."

### Saving #1: Smart Batching — $547,000 per Year

> "Without smart batching, if we average 50 files per Black Box 1 call:"
> "10 million files ÷ 50 = 200,000 calls per day × $0.01 = **$2,000 per day**"

> "With smart batching, always filling to 200:"
> "10 million files ÷ 200 = 50,000 calls per day × $0.01 = **$500 per day**"

> "Savings: $1,500 per day = **$547,000 per year**. And this works regardless of whether files are unique."

### Saving #2: Parallelism Reduces Compute — $96,000 per Year

> "Without parallelism, each worker processes Black Box 1 calls one at a time. To handle 1,000 files per second, we need roughly 20 worker machines."

> "With parallelism, each worker fires 10 Black Box 1 calls simultaneously, making each worker 5 times more productive. We need only 4 machines instead of 20."

> "At roughly $500 per month per machine: 16 fewer machines × $500 = **$8,000 per month = $96,000 per year**."

### Saving #3: Queue Prevents Over-Provisioning — $60,000+ per Year

> "Without a queue, we have to provision enough machines to handle our worst-case traffic spike. If our normal load needs 5 machines but spikes need 30, we're paying for 30 machines around the clock even though 25 sit idle most of the time."

> "With a queue, spikes are absorbed. We run 5 machines normally and only scale up if the queue depth stays high for an extended period. The savings depend on how spiky traffic is, but for a system with 10x spikes, we're avoiding $60,000 or more per year in idle machine costs."

### Saving #4 (Conditional): Embedding Cache — Varies

> "If the workload involves repeated content — like content moderation — a cache with 50% hit rate would cut Black Box 1 calls in half on top of the batching savings. That's another $250,000+ per year."

> "If the workload is all unique content, the cache saves close to zero. This is why I'd instrument it rather than assume."

### Total

> "The guaranteed savings from batching, parallelism, and queue management: roughly **$700,000 per year**. Caching could add another $250,000+ depending on the use case. And these numbers scale linearly — double the volume, double the savings."

---

## Latency Breakdown — Real-Time Path (3 Minutes)

### What to Say

> "Let me walk through the timing for a real-time request with 50 unique files — worst case, no cache hits:"

```
Step                                        Time
────                                        ────
Gateway authentication + routing:            10ms
Orchestrator receives request:                5ms
[Optional] Check embedding cache:             5ms → 0 hits (worst case)
Call Black Box 1 (50 files, 1 call):        400ms ← Biggest chunk
Save new embeddings (background):             0ms (fire and forget)
Call Black Box 2 (50 embeddings, 1 call):   200ms
Save results (background):                    0ms (fire and forget)
Return response to customer:                  5ms
                                           ─────
Total:                                     ~625ms ✅ Under 1 second
```

> "We have 375 milliseconds of headroom. Even if Black Box 1 is a bit slow one day, we still make it."

> "For a larger request — say 500 files — we'd make 3 parallel Black Box 1 calls of ~167 files each. Total time is still about 625 milliseconds because the calls run simultaneously."

> "The breaking point is when Black Box 1 latency increases. If it jumps to 800 milliseconds on a bad day, we'd be at 1,015 milliseconds — slightly over budget. That's when the cache becomes valuable even for unique content: if we can pull even 10% of embeddings from cache, it reduces the work Black Box 1 has to do per call, potentially bringing down the per-call latency."

---

## Throughput Path Math (3 Minutes)

### What to Say

> "For the batch path targeting 1,000 files per second:"

```
Black Box 1:
  1,000 files per second ÷ 200 per call = 5 calls per second
  Each call takes 400ms
  One worker can do: 1000ms ÷ 400ms = 2.5 calls per second
  Workers needed: 5 ÷ 2.5 = 2 workers for Black Box 1

Black Box 2:
  1,000 embeddings per second ÷ 2,000 per call = 0.5 calls per second
  One call every 2 seconds — a single worker handles this easily

Total workers needed: 3 (2 for embedding, 1 for classification)
```

> "With parallelism, each worker fires multiple calls simultaneously, so we can likely get away with even fewer. The queue accumulates files until we have a full batch of 200, maximizing efficiency."

> "If we need to scale to 10,000 files per second, we scale horizontally — add more workers pulling from the queue. 10x the throughput requires roughly 10x the workers, which the queue handles naturally."

---

## Failure Handling (5 Minutes)

### Scenario 1: Black Box 1 Stops Responding

> "We use a pattern called a **circuit breaker**. We track failed calls. If failures exceed a threshold — say 5 in a row — we stop sending requests to Black Box 1 for 30 seconds. This prevents us from piling up thousands of doomed requests against a broken service."

> "During the outage: real-time requests get an error response saying 'service temporarily unavailable, retry in 30 seconds.' Batch tasks stay in the queue — they'll be processed when the service recovers."

> "After 30 seconds, we try one test request. If it works, we resume normal operation. If it fails, we wait another 30 seconds."

### Scenario 2: Worker Crashes Mid-Processing

> "This is why the queue matters. When a worker picks up a task, the task becomes invisible but isn't deleted. If the worker finishes, it deletes the task. If the worker crashes, the task reappears after a timeout and another worker picks it up."

> "Retrying is safe because both Black Box 1 and Black Box 2 are deterministic — same input always gives same output. Processing a chunk twice produces identical results."

### Scenario 3: Redis Goes Down

> "If Redis crashes, we lose the cache and rate limit counters. The system keeps working — every request becomes a cache miss, so we make more Black Box 1 calls. It's slower and more expensive temporarily, but nothing breaks. This is called **graceful degradation**."

### Scenario 4: Database Is Slow

> "For real-time requests, this doesn't matter — storage writes happen in the background after we've already responded. The customer never notices."

> "For batch jobs, progress updates might lag slightly, but processing continues normally."

---

## Wrap-Up — Three Key Points (1 Minute)

> "To summarize the three most important decisions in this design:"

> "**First — parallelism.** Running Black Box 1 calls simultaneously instead of sequentially is the single biggest performance win. It cuts embedding time by 80% or more and works for every request regardless of content."

> "**Second — smart batching and the fan-out/fan-in pattern.** We exploit the asymmetric limits — fan out across many Black Box 1 calls, fan in to one Black Box 2 call. Always fill batches to capacity. This cuts costs by 75%."

> "**Third — separate paths for separate needs.** Real-time optimizes for speed: small batches, no queuing, background storage. Batch optimizes for cost: full batches, queue-based processing, maximum throughput. Each path makes different trade-offs because the customers have different priorities."

---

## Quick Answers to Likely Follow-Up Questions

**"What about caching?"**
> "I built it as a conditional optimization. The guaranteed wins — parallelism, batching, async writes — don't depend on content being repeated. The cache is there if the workload benefits from it. I'd instrument the hit rate and make a data-driven decision about how much to invest in it."

**"How would you deploy this?"**
> "Each service runs in its own container — a lightweight, portable package of code and dependencies. I'd use a container orchestration platform to manage them: starting more containers when load increases, replacing containers that crash, and rolling out new versions without downtime."

**"What happens when the model updates?"**
> "Embeddings are generated by a specific model version. When the model updates, embeddings from the old version are no longer valid for the new model. I'd include the model version in any cache keys and in the storage metadata. Old embeddings naturally expire, and we regenerate as needed."

**"What if a single customer sends 100,000 files?"**
> "That goes through the batch path. The ingestion service creates a job record, chunks 100,000 files into 500 tasks of 200, and drops them all in the queue. With 10 workers running in parallel, each processing a batch in about 400 milliseconds, that's roughly 200 seconds to process everything. The customer gets their job identifier instantly and checks back for progress."

**"How do you prevent duplicate work?"**
> "Two levels. First, in the batch path, each task has a unique identifier. Before processing, the worker checks if results already exist for that task. If so, skip it. This handles retries safely. Second, if two customers happen to submit the same file at exactly the same time, I could implement request coalescing — detect that the file is already being processed and wait for that result instead of making a duplicate call. But I'd only build that if monitoring shows it's a real problem."

**"What metrics would you monitor?"**
> "Four categories: **Speed** — request latency at the 50th, 95th, and 99th percentiles. **Volume** — requests per second, queue depth, batch sizes, files processed per hour. **Errors** — failure rates for each black box, timeout rates, circuit breaker activations. **Cost** — number of black box calls per hour, cache hit rate if enabled, compute utilization per worker, and storage growth rate."

**"Why not use a vector database for embeddings?"**
> "We're not doing similarity search — we're doing exact key-value lookup. 'Give me the embedding for this specific file hash.' That's a simple lookup, not a nearest-neighbor search. Redis handles that perfectly. A vector database would add complexity and cost without benefit for this use case."
