# Scaling Recommendations

Campaign Performance Loop turns imported metrics into proposed decisions.

Rules:

- high views and high engagement -> `scale_variant`;
- high views and low clicks -> `regenerate_variant`;
- high clicks and low orders -> `regenerate_variant`;
- low views on a destination -> `change_destination`;
- high cost per order -> `pause_variant`;
- published content without stats -> `import_performance_stats`;
- strong variant across multiple destinations -> `increase_distribution`.

Integration with Campaign Execution:

- regeneration recommendations can create safe `create_regeneration_request` queue items;
- scaling recommendations can create safe draft action queue items;
- live publishing, approval, paid generation, and external upload stay gated.
