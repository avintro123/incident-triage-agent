# Runbook: Redis Cluster Memory Exhaustion and OOM Crashes
<!-- 
  NOTE FOR BEGINNERS:
  This is a Markdown file (.md). Software engineers use Markdown to write manuals (runbooks).
  - Lines starting with '#' are big chapter titles.
  - Lines starting with '##' are section subheadings.
  - Tables are created using '|' characters.
  - Code blocks are wrapped inside triple backticks (```).
-->

## 1. Overview and Symptoms
During peak traffic spikes, the caching cluster may encounter memory pressure.
Primary alerts triggered:
* Alert: `REDIS_MEM_CRITICAL` (Used memory exceeds 92% of maxmemory)
* Error Code: `ERR_OOM_COMMAND_NOT_ALLOWED` (Redis rejects write commands because memory is full)
* User Impact: The checkout website responds with `504 Gateway Timeout`

## 2. Diagnostics Commands
Run these commands in the terminal to inspect the server:
```bash
# Check memory allocation and fragmentation ratio
redis-cli -h cache.prod.internal -p 6379 info memory

# Find which keys are consuming the most memory
redis-cli --bigkeys
```

| Metric Name | Safe Threshold | Danger Threshold | Action Required |
| :--- | :--- | :--- | :--- |
| `used_memory_rss` | < 12 GB | > 14.5 GB | Trigger memory purge |
| `mem_fragmentation_ratio` | 1.0 - 1.3 | > 1.8 | Run active defragmentation |

## 3. Mitigation and Recovery Steps
Follow these steps in strict sequence:
1. **Enable Active Defragmentation immediately:**
   ```bash
   redis-cli config set activedefrag yes
   ```
2. **Evict non-critical session caches:**
   Run the eviction script to free up space:
   ```bash
   python /opt/scripts/evict_transient_sessions.py --ttl-hours 2
   ```

## 4. Post-Incident Review
Log a ticket under component `Infrastructure-Database` referencing error `REDIS_MEM_CRITICAL`.

