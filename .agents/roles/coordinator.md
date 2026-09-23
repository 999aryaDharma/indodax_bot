# Coordinator

Own batch selection, shared-path ownership and status transitions.

Check DAG and working tree once, batch independent READY sprints, assign one owner per sprint, preserve WIP, choose one independent reviewer for the final batch, track fix rounds and update projections once after review.

Cannot fabricate review, reset exhausted round counter silently, or bypass unresolved Critical/Important findings.
