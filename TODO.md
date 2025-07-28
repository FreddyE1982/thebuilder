# TODO

1. Add integration tests for API endpoints to ensure proper database access.
2. Add tests for GUI components described in streamlittestinghowto.md.
3. Refactor rest_api.py to group routes by resource using APIRouter.
4. Document API endpoints with OpenAPI descriptions.
5. Add user authentication and authorization for workout editing.
6. Implement pagination on workout history API.
7. Create CLI to export workouts to CSV and JSON.
8. Add scheduling for regular email reports.
9. Improve planner_service with goal-based plan suggestions.
10. Validate YAML settings via schema on startup.
11. Add backup/restore commands for the SQLite database.
12. Add continuous integration workflow running tests on push.
13. Expand statistics to include per-muscle progress charts.
14. Add endpoint for editing wellness logs.
15. Create responsive mobile layout tests for each GUI tab.
16. Include weight unit conversion support in stats_service.
17. Add dark/light theme switch stored in settings.
18. Implement two-factor authentication for new user login.
19. Add localization framework for multi-language UI.
20. Refactor database layer to async for FastAPI performance.
21. Add unit tests for ml_service models.
22. Provide interactive charts for power and velocity histories.
23. Add endpoint for exercise alias removal.
24. Implement caching for statistics queries using SQLite views.
25. Add Jenkinsfile for automated build.
26. Add color-blind friendly theme options.
27. Implement rate limiting on REST API endpoints.
28. Add importer from widely-used workout apps (e.g. Strava).
29. Provide export to generic training XML format.
30. Add websockets endpoint for real-time workout updates.
31. Implement progressive web app features for offline use.
32. Add endpoint to download body_weight_logs as CSV.
33. Provide monthly summary emails via Cron or Celery.
34. Add user-defined default equipment per exercise.
35. Implement privacy settings for shared workouts.
36. Add voice command support in the GUI.
37. Add voice feedback for timer events using STT.
38. Refactor tools.py to separate math utilities from CLI utilities.
39. Add coverage reporting to tests.
40. Document environment variables for deployment in README.
41. Add support for external database like PostgreSQL.
42. Add repository pattern for ml_service states.
43. Add progress bar to Streamlit when uploading CSV files.
44. Provide data validation on CSV imports.
45. Add 3D visualization of muscle engagement.
46. Support image upload for exercise demonstration.
47. Add endpoint for goal progress chart data.
48. Create docker-compose configuration for local dev.
49. Add ability to clone templates between users.
50. Support configurable RPE scale (e.g. 1–5 or 1–10).
51. Add analytics for training monotony and strain.
52. Provide webhooks for completed workouts notifications.
53. Add route to mark challenges as completed automatically.
54. Implement search for exercises by tags in GUI.
55. Support uploading heart rate monitor data in bulk.
56. Extend rest_api tests to cover error conditions.
57. Add dynamic equipment suggestion using ML predictions.
58. Provide sample data seeding script.
59. Add instructions for customizing CSS in README.
60. Ensure StatsService returns sorted results consistently.
61. Add REST endpoint for editing exercise catalog entries.
62. Provide ability to share workout templates via link.
63. Add feature flag support for experimental models.
64. Implement timeline view of workout history in GUI.
65. Improve error messages for invalid API input.
66. Store original raw data of ML training sets.
67. Add cross-validation for ML models to compute accuracy.
68. Include predicted confidence intervals in API responses.
69. Support dynamic chart resizing depending on metrics.
70. Implement advanced search filters in planner_service.
71. Provide endpoint to add comments to workouts.
72. Add rating distribution chart in Stats tab.
73. Validate equipment type names to avoid duplicates.
74. Document database schema in README.
75. Add `--demo` mode for generating fake data.
76. Encrypt sensitive settings in YAML with keyring.
77. Add endpoint to clear cached statistics.
78. Provide gender-neutral avatar images in GUI.
79. Implement plugin architecture for custom ML models.
80. Add data migration script for schema changes.
81. Implement Slack notifications for workout logs.
82. Add API key management for third-party integrations.
83. Provide user-friendly onboarding wizard in GUI.
84. Add long-term trend analytics (moving averages).
85. Support per-workout timezone handling.
86. Implement automatic database vacuuming.
87. Add drag-and-drop reordering for workout templates.
88. Integrate speech recognition for quick set entry.
89. Create official REST client library in Python.
90. Add performance benchmarks for API endpoints.
91. Provide security audit of dependencies via tools.
92. Add automatic detection of stale goals.
93. Offer periodic data export via email link.
94. Add ability to log mood before/after workouts.
95. Implement color-coded workout intensity map.
96. Add endpoint to configure auto planner parameters.
97. Support split view on tablets for side-by-side charts.
98. Provide API to fetch saved report PDFs.
99. Add screenshot-based test for mobile layout via playwright.
100. Document contribution guidelines and code style.

