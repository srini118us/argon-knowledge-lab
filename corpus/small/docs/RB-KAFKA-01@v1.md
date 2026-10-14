```
Document ID : RB-KAFKA-01
Version     : v1
Title       : Kafka consumer lag
Date        : 2025-07-01
Status      : Current
```

# Runbook: Kafka consumer lag

**Platform owner:** The Kafka platform is owned by the **Platform team**. Platform runs the brokers, topic configuration, access control and the shared monitoring. The teams that own consuming services own their consumers.

**Alert:** Consumer lag alert threshold is **50,000 messages**. The alert fires when a consumer group's lag on a topic goes above 50,000 messages.

---

## What is consumer lag?

Lag is the gap between the newest message written to a partition and the last message a consumer group has committed for that partition, summed across the partitions of the topic. A small, steady lag is normal: consumers are always slightly behind producers. Lag that keeps growing means the consumer group cannot keep up, has stopped, or is stuck on something.

Since Orion moved its event bus from RabbitMQ to Apache Kafka, lag has become the main signal we use to tell whether event driven work (notifications, reporting, downstream updates) is happening on time. In RabbitMQ terms, it plays roughly the role that queue depth used to.

## When this alert fires

You are probably the on-call engineer for the team that owns the consumer named in the alert. If you are the Platform on-call and the alert names a consumer you do not own, your first job is to work out whether this is a platform problem or a consumer problem (step 2 below), then route accordingly.

### Step 1: Get the picture

Open the Kafka consumer lag dashboard and find the consumer group from the alert. Look at:

- **Shape of the lag curve.** A sudden spike that is already falling is often a burst of producer traffic and will clear by itself. A straight line going up means the consumer is not processing at all. A slow climb means it is processing, but slower than messages arrive.
- **Per partition lag.** Lag concentrated on one or two partitions points at a stuck consumer instance or a poison message. Lag spread evenly across all partitions points at overall throughput.
- **Consumer group membership.** Check how many members the group has and whether it has been rebalancing repeatedly.

You can also check from the CLI:

```bash
kafka-consumer-groups.sh --bootstrap-server "$KAFKA_BOOTSTRAP" \
  --describe --group <consumer-group>
```

The `LAG` column is per partition. `CONSUMER-ID` of `-` means nobody is assigned to that partition.

### Step 2: Platform or consumer?

Ask in the Platform channel or check the Platform status page. Signs it is a platform problem:

- several unrelated consumer groups lagging at the same time
- producer errors in services that write to Kafka
- broker health alerts from the Platform monitoring

If it looks like a platform problem, page the Platform on-call and stop here. Do not start restarting consumers, which will just add rebalances to an already unhappy cluster.

If only your consumer group is affected, carry on.

### Step 3: Common consumer causes

**Consumer is down or crash looping.** Check the deployment for the consuming service. Recent deploy? Roll back first and investigate after.

**Poison message.** A message the consumer cannot process, retried forever, blocks one partition. Logs will show the same offset failing over and over. Follow the owning team's procedure for skipping or parking the message. Do not reset offsets for the whole group to get past one bad message.

**Rebalance storm.** If members keep joining and leaving, processing barely happens. Usually caused by consumers taking longer than the poll interval to process a batch. Look for slow downstream calls from the consumer.

**Slow downstream dependency.** The consumer is fine but each message waits on a database or another service. Lag climbs steadily. Fix or mitigate the dependency; scaling consumers will not help if the dependency is the bottleneck.

**Genuine traffic increase.** Lag spread evenly, consumers healthy, just more messages than usual. Scale the consumer out, up to the number of partitions on the topic. Beyond that, extra instances sit idle.

### Step 4: Recovery

Once the cause is fixed, watch the lag fall. Lag usually drains faster than it built, because consumers are now running flat out. Keep the incident open until lag is back below the alert threshold and stable.

Remember topic retention. Messages are not kept forever, and a consumer that stays behind long enough can lose messages it never read. If lag has been building for a long time, check with Platform how close the oldest unread offsets are to the retention boundary, and raise it as an urgent issue if they are close.

## Things not to do

- Do not reset consumer group offsets to latest to "clear" an alert. You will silently skip every unprocessed message.
- Do not change topic configuration yourself. Topic settings are owned by Platform; ask them.
- Do not delete and recreate a consumer group as a fix.

## Escalation

| Situation | Who |
|---|---|
| Single consumer group lagging, consumer side cause | Owning team on-call |
| Multiple groups lagging, or broker or producer errors | Platform on-call |
| Lag approaching retention, risk of data loss | Platform on-call and the owning team lead |

## After the incident

If the alert fired because of something that will happen again (a known traffic peak, a slow dependency), write it up and talk to Platform about whether the consumer needs more partitions or a different design. The threshold itself is set by Platform; if you think it is wrong for your topic, raise it with them rather than muting the alert.
