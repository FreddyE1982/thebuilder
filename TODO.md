# TODO

[complete] 1. Add integration tests for API endpoints to ensure proper database access.
[complete] 2. Add tests for GUI components described in streamlittestinghowto.md.
[complete] 3. Refactor rest_api.py to group routes by resource using APIRouter.
[complete] 4. Document API endpoints with OpenAPI descriptions.
[removed] 5a. Remove user and token tables and login endpoints.
[removed] 5b. Associate workouts with user accounts (multiuser removed).
[removed] 5c. Enforce authentication for workout editing (multiuser removed).
[complete] 6. Implement pagination on workout history API.
[complete] 7. Create CLI to export workouts to CSV and JSON.
[complete] 8. Add scheduling for regular email reports.
[complete] 9. Improve planner_service with goal-based plan suggestions.
[complete] 10. Validate YAML settings via schema on startup.
[complete] 11. Add backup/restore commands for the SQLite database.
[complete] 12. Add continuous integration workflow running tests on push.
[complete] 13. Expand statistics to include per-muscle progress charts.
[complete] 14. Add endpoint for editing wellness logs.
[complete] 15. Create responsive mobile layout tests for each GUI tab.
[complete] 16. Include weight unit conversion support in stats_service.
[complete] 17. Add dark/light theme switch stored in settings.
[removed] 18. Remove two-factor authentication and login features (multiuser removed).
[complete] 19. Add localization framework for multi-language UI.
[complete] 19b. Integrate translations for UI labels.
[complete] 19c. Add language selector in settings.
[complete] 20a. Create asynchronous repository layer using aiosqlite.
20b1. Convert WorkoutRepository to AsyncWorkoutRepository. [complete]
20b2. Convert remaining repositories to async versions.
20c1. Update REST API workouts endpoints to async. [pending]
20c2. Update remaining endpoints to async.
20d1. Add tests for AsyncWorkoutRepository. [complete]
20d2. Update remaining tests for async operations.
[complete] 21. Add unit tests for ml_service models.
[complete] 22. Provide interactive charts for power and velocity histories.
[complete] 23. Add endpoint for exercise alias removal.
[complete] 24. Implement caching for statistics queries using SQLite views.
[complete] 25. Add Jenkinsfile for automated build.
[complete] 26. Add color-blind friendly theme options.
[complete] 27. Implement rate limiting on REST API endpoints.
[complete] 28. Add importer from widely-used workout apps (e.g. Strava).
[complete] 29. Provide export to generic training XML format.
[complete] 30. Add websockets endpoint for real-time workout updates.
31. Implement progressive web app features for offline use.
[complete] 32. Add endpoint to download body_weight_logs as CSV.
[complete] 33. Provide monthly summary emails via Cron or Celery.
[complete] 34. Add user-defined default equipment per exercise.
[removed] 35. Remove privacy settings for shared workouts (multiuser removed).
36. Add voice command support in the GUI.
[complete] 37. Add voice feedback for timer events using STT.
[complete] 38. Refactor tools.py to separate math utilities from CLI utilities.
[complete] 39. Add coverage reporting to tests.
[complete] 40. Document environment variables for deployment in README.
41. Add support for external database like PostgreSQL.
[complete] 42. Add repository pattern for ml_service states.
[complete] 43. Add progress bar to Streamlit when uploading CSV files.
[complete] 44. Provide data validation on CSV imports.
[complete] 45. Add 3D visualization of muscle engagement.
[complete] 46. Support image upload for exercise demonstration.
[complete] 47. Add endpoint for goal progress chart data.
[complete] 48. Create docker-compose configuration for local dev.
[removed] 49. Remove ability to clone templates between users (multiuser removed).
[complete] 50. Support configurable RPE scale (e.g. 1–5 or 1–10).
[complete] 51. Add analytics for training monotony and strain.
[complete] 52. Provide webhooks for completed workouts notifications.
[complete] 53. Add route to mark challenges as completed automatically.
[complete] 54. Implement search for exercises by tags in GUI.
[complete] 55. Support uploading heart rate monitor data in bulk.
[complete] 56. Extend rest_api tests to cover error conditions.
57. Add dynamic equipment suggestion using ML predictions.
[complete] 58. Provide sample data seeding script.
[complete] 59. Add instructions for customizing CSS in README.
[complete] 60. Ensure StatsService returns sorted results consistently.
[complete] 61. Add REST endpoint for editing exercise catalog entries.
[removed] 62. Remove ability to share workout templates via link (multiuser removed).
[complete] 63. Add feature flag support for experimental models.
[complete] 64. Implement timeline view of workout history in GUI.
[complete] 65. Improve error messages for invalid API input.
[complete] 66. Store original raw data of ML training sets.
[complete] 67. Add cross-validation for ML models to compute accuracy.
[complete] 68. Include predicted confidence intervals in API responses.
[complete] 69. Support dynamic chart resizing depending on metrics.
70. Implement advanced search filters in planner_service.
[complete] 71. Provide endpoint to add comments to workouts.
[complete] 72. Add rating distribution chart in Stats tab.
[complete] 73. Validate equipment type names to avoid duplicates.
[complete] 74. Document database schema in README.
[complete] 75. Add `--demo` mode for generating fake data.
76. Encrypt sensitive settings in YAML with keyring.
[complete] 77. Add endpoint to clear cached statistics.
[complete] 78. Provide gender-neutral avatar images in GUI.
79. Implement plugin architecture for custom ML models.
[complete] 80. Add data migration script for schema changes.
[complete] 81. Implement Slack notifications for workout logs.
[complete] 82. Add API key management for third-party integrations.
[complete] 83. Provide user-friendly onboarding wizard in GUI.
[complete] 84. Add long-term trend analytics (moving averages).
[complete] 85. Support per-workout timezone handling.
[complete] 86. Implement automatic database vacuuming.
[complete] 87. Add drag-and-drop reordering for workout templates.
88. Integrate speech recognition for quick set entry.
89. Create official REST client library in Python.
[complete] 90. Add performance benchmarks for API endpoints.
[complete] 91. Provide security audit of dependencies via tools.
[complete] 92. Add automatic detection of stale goals.
[complete] 93. Offer periodic data export via email link.
[complete] 94. Add ability to log mood before/after workouts.
[complete] 95. Implement color-coded workout intensity map.
[complete] 96. Add endpoint to configure auto planner parameters.
[complete] 97. Support split view on tablets for side-by-side charts.
[complete] 98. Provide API to fetch saved report PDFs.
99. Add screenshot-based test for mobile layout via playwright.
[complete] 100. Document contribution guidelines and code style.

[complete] 101. Add interactive calendar to schedule workouts.
[complete] 102. Add global search bar for workouts and exercises.
[complete] 103. Provide quick-add popup for workouts from home.
[complete] 104. Add drag-and-drop reordering for planned workouts.
[complete] 105. Add time-based filter in workout history.
[complete] 106. Provide color-coded heatmap of training volume per week.
107. Add speech-to-text input for set entry.
[complete] 108. Provide inline video tutorials for each exercise.
[complete] 109. Allow checkboxes to mark sets as warm-ups.
[complete] 110. Add screenshot capture for progress charts.
[complete] 111. Enable duplication of logged workouts.
[complete] 112. Support export of progress charts to PDF.
[complete] 113. Show real-time timer overlay during sets.
[complete] 114. Filter exercise lists to favorites only.
[complete] 115. Display workout completion progress bar.
[complete] 116. Auto start rest timer after each set.
[complete] 117. Customize quick weight buttons in settings.
[complete] 118. Allow hiding of completed sets.
[complete] 119. Collapse exercises into expandable sections.
[complete] 120. Color-code workouts by training type tags.
[complete] 121. Copy weight values to clipboard with one click.
[complete] 122. Set custom accent color in settings.
123. Generate shareable read-only workout summary images.
[complete] 124. Undo deletion of sets.
[complete] 125. Create templates from logged workouts.
126. Step-by-step onboarding for new features.
127. Offline caching of recent workouts.
128. Weekly planner view for upcoming sessions.
129. Voice output for rest timer countdown.
[complete] 130. Quick-add notes using predefined phrases.
131. Compare progress between two exercises.
[complete] 132. Sort exercise library by various fields.
[complete] 133. Rate workouts using star ratings.
[complete] 134. Toggle to hide navigation labels.
[complete] 135. Pin key metrics on the dashboard.
[complete] 136. Collapsible filter panel in history tab.
[complete] 137. Keyboard shortcuts help overlay.
138. Bulk edit multiple sets at once.
139. Randomize training plan generator.
[complete] 140. Filter exercises without equipment assigned.
[complete] 141. Switch weight units on the fly in set entry.
142. Assign custom icons to workouts.
[complete] 143. Multi-select deletion of planned workouts.
144. Donut charts for goal progress visualization.
[complete] 145. Link directly to equipment details from sets.
146. Interactive tutorial for first workout creation.
[complete] 147. Hotkey to repeat last set quickly.
[complete] 148. Inline editing of tags.
[complete] 149. Simple mode toggle hiding advanced fields.
[complete] 150. Color-code sets by intensity level.
[complete] 151. Adjustable font size slider in settings.
152. Import images using mobile share menu.
153. Quick-add rest notes after each set.
154. Contextual help tips on each page.
[complete] 155. Toggle display of estimated 1RM.
156. Indicator for unsaved changes in forms.
[complete] 157. Collapsible summary metrics in history.
158. Step counter integration for cardio.
159. Quick access to recently used templates.
[complete] 160. Mini progress widget on home screen.
161. Filter results by muscle group across tabs.
[complete] 162. Dynamic search suggestions for exercises.
[complete] 163. Highlight personal record sets automatically.
164. Short completion animations for workouts.
[complete] 165. Quick-add tags using hashtag syntax.
166. Scrollable timeline of workout months.
[complete] 167. Rename logged workouts.
[complete] 168. Customizable layout spacing options.
[complete] 169. Filter by equipment type quickly.
[complete] 170. Hide or show columns in tables.
[complete] 171. Label rest timer progress with percent.
[complete] 172. Schedule dark mode automatically at night.
[complete] 173. Toggle to hide advanced charts.
[complete] 174. Built-in calculator for weight conversions.
175. Voice prompts for workout start and stop.
[complete] 176. Favorite templates directly from history.
[complete] 177. "Open last workout" button on start page.
178. Interactive personal record tracker.
[complete] 179. Quick-add macro entries to notes.
[complete] 180. Color-code templates for organization.
[complete] 181. Automatic cleanup of empty workouts.
[complete] 182. Highlight new personal record improvements.
[complete] 183. Vertical orientation option for bottom nav.
[complete] 184. "What's new" dialog after updates.
[complete] 185. Quick start workout from plan list.
[complete] 186. Print-friendly workout summary view.
[complete] 187. High-contrast accessibility theme.
[complete] 188. Option to auto-collapse header on scroll.
[complete] 189. Import workout history from CSV.
190. Local search index for offline filtering.
191. Daily reminder notifications.
[complete] 192. Quick filter for unrated workouts.
[complete] 193. Keyboard navigation in history table.
[complete] 194. Customizable quick weight increments.
[complete] 195. Bulk mark sets as completed using checkboxes.
[complete] 196. Collapsible explanations for analytics charts.
[complete] 197. Preview thumbnails for uploaded images.
[complete] 198. Keyboard shortcut to toggle dark mode.
[complete] 199. Flexible grid layout toggle.
[complete] 200. "Clear filters" button in history tab.
[complete] 201. Remove all multiuser features from the code base.
