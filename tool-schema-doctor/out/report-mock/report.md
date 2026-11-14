# Tool-Schema Doctor — Report

- Generated: `2026-11-13T18:59:17+00:00`
- Input: `composio-upstream/ts/packages/cli/test/__mocks__/tools.json` (source: **mock**)
- Tools: **930** · with schema: 930 · with tags: 892

## Provider compatibility
| Provider | ok | transformed | error | unavailable | skipped |
|---|---|---|---|---|---|
| `anthropic` | 930 | 0 | 0 | 0 | 0 |
| `gemini` | 0 | 929 | 1 | 0 | 0 |
| `google_adk` | 6 | 924 | 0 | 0 | 0 |
| `google_vertex` | 13 | 911 | 6 | 0 | 0 |
| `openai` | 930 | 0 | 0 | 0 | 0 |
| `openai_strict` | 0 | 816 | 114 | 0 | 0 |

### Failing conversions (121)
| Tool | Provider | Error | Schema path |
|---|---|---|---|
| `GOOGLEDRIVE_UPDATE_PERMISSION` | `gemini` | ValueError: Failed to parse the parameter permission: composio.utils.schema_converter.Permission of  | `/properties/permission` |
| `GOOGLEDRIVE_FILES_MODIFY_LABELS` | `google_vertex` | ParseError: Failed to parse properties field: Failed to parse items field: Failed to parse propertie | `/properties/label_modifications/items/properties/field_modifications/items/properties/set_date_values/examples` |
| `GOOGLEDRIVE_UPDATE_PERMISSION` | `google_vertex` | ParseError: Failed to parse properties field: Failed to parse properties field: Message type "google | `/properties/permission/properties/role/examples` |
| `GOOGLEDRIVE_UPLOAD_FILE` | `google_vertex` | ParseError: Failed to parse properties field: Message type "google.cloud.aiplatform.v1beta1.Schema"  | `/properties/file_to_upload/file_uploadable` |
| `GOOGLE_ANALYTICS_CREATE_EXPANDED_DATA_SET` | `google_vertex` | ParseError: Failed to parse properties field: Failed to parse properties field: Message type "google | `/properties/expandedDataSet/properties/dimensionNames/examples` |
| `GOOGLE_CLASSROOM_COURSE_WORK_PATCH` | `google_vertex` | ParseError: Failed to parse properties field: Failed to parse properties field: Message type "google | `/properties/dueDate/properties/day/examples` |
| `GOOGLE_MAPS_MAPS_EMBED_API` | `google_vertex` | ParseError: Failed to parse properties field: Failed to parse properties field: Message type "google | `/properties/directions_params/properties/avoid/examples` |
| `GITHUB_ADD_AN_EMAIL_ADDRESS_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: properties.emails.items: properties | `` |
| `GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE` | `openai_strict` | ValueError: strict-unsupported: properties.assignees.items: properties | `` |
| `GITHUB_ADD_ORG_RUNNER_LABELS` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_ADD_RUNNER_LABELS` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_ADD_SOCIAL_ACCOUNTS_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: properties.account_urls.items: properties | `` |
| `GITHUB_ADD_USERS_TO_CODESPACES_ACCESS_FOR_AN_ORGANIZATION` | `openai_strict` | ValueError: strict-unsupported: properties.selected_usernames.items: properties | `` |
| `GITHUB_AUTH_USER_DOCKER_CONFLICT_PACKAGES_LIST` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_CONFIGURE_JITRUNNER_FOR_ORG` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_CONFIGURE_OIDCSUBJECT_CLAIM_TEMPLATE` | `openai_strict` | ValueError: strict-unsupported: properties.include_claim_keys.items: properties | `` |
| `GITHUB_CREATE_AN_ISSUE` | `openai_strict` | ValueError: strict-unsupported: properties.assignees.items: properties; properties.labels.items: pro | `` |
| `GITHUB_CREATE_AN_ORGANIZATION_REPOSITORY` | `openai_strict` | ValueError: strict-unsupported: properties.custom_properties: additionalProperties | `` |
| `GITHUB_CREATE_AN_ORGANIZATION_VARIABLE` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_CREATE_AN_ORGANIZATION_WEBHOOK` | `openai_strict` | ValueError: strict-unsupported: properties.events.items: properties | `` |
| `GITHUB_CREATE_A_CHECK_RUN` | `openai_strict` | ValueError: strict-unsupported: properties.actions.items: additionalProperties; properties.output__a | `` |
| `GITHUB_CREATE_A_COMMIT` | `openai_strict` | ValueError: strict-unsupported: properties.parents.items: properties | `` |
| `GITHUB_CREATE_A_CUSTOM_ORGANIZATION_ROLE` | `openai_strict` | ValueError: strict-unsupported: properties.permissions.items: properties | `` |
| `GITHUB_CREATE_A_DEPLOYMENT` | `openai_strict` | ValueError: strict-unsupported: properties.required_contexts.items: properties | `` |
| `GITHUB_CREATE_A_GIST` | `openai_strict` | ValueError: strict-unsupported: properties.files.additionalProperties: additionalProperties; propert | `` |
| `GITHUB_CREATE_A_REPOSITORY_DISPATCH_EVENT` | `openai_strict` | ValueError: strict-unsupported: properties.client_payload: additionalProperties | `` |
| `GITHUB_CREATE_A_REPOSITORY_RULESET` | `openai_strict` | ValueError: strict-unsupported: properties.bypass_actors.items: additionalProperties; properties.con | `` |
| `GITHUB_CREATE_A_REPOSITORY_WEBHOOK` | `openai_strict` | ValueError: strict-unsupported: properties.events.items: properties | `` |
| `GITHUB_CREATE_A_SCOPED_ACCESS_TOKEN` | `openai_strict` | ValueError: strict-unsupported: properties.repositories.items: properties; properties.repository_ids | `` |
| `GITHUB_CREATE_A_SNAPSHOT_OF_DEPENDENCIES_FOR_A_REPOSITORY` | `openai_strict` | ValueError: strict-unsupported: properties.manifests.additionalProperties: additionalProperties; pro | `` |
| `GITHUB_CREATE_A_TEAM` | `openai_strict` | ValueError: strict-unsupported: properties.maintainers.items: properties; properties.repo_names.item | `` |
| `GITHUB_CREATE_A_TREE` | `openai_strict` | ValueError: strict-unsupported: properties.tree.items: additionalProperties | `` |
| `GITHUB_CREATE_A_WORKFLOW_DISPATCH_EVENT` | `openai_strict` | ValueError: strict-unsupported: properties.inputs: additionalProperties | `` |
| `GITHUB_CREATE_JIT_RUNNER_CONFIG` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_CREATE_OR_UPDATE_AN_ENVIRONMENT` | `openai_strict` | ValueError: strict-unsupported: properties.reviewers.items: additionalProperties | `` |
| `GITHUB_CREATE_OR_UPDATE_AN_ORGANIZATION_SECRET` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_CREATE_OR_UPDATE_A_CUSTOM_PROPERTY_FOR_AN_ORGANIZATION` | `openai_strict` | ValueError: strict-unsupported: properties.allowed_values.items: properties | `` |
| `GITHUB_CREATE_OR_UPDATE_A_SECRET_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_CREATE_OR_UPDATE_CUSTOM_PROPERTIES_FOR_AN_ORGANIZATION` | `openai_strict` | ValueError: strict-unsupported: properties.properties.items: additionalProperties | `` |
| `GITHUB_CREATE_OR_UPDATE_CUSTOM_PROPERTY_VALUES_FOR_A_REPOSITORY` | `openai_strict` | ValueError: strict-unsupported: properties.properties.items: additionalProperties | `` |
| `GITHUB_CREATE_UPDATE_ORG_SECRET_WITH_LIB_SODIUM` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_CUSTOM_OIDCSUBJECT_CLAIM_TEMPLATE_SETTER` | `openai_strict` | ValueError: strict-unsupported: properties.include_claim_keys.items: properties | `` |
| `GITHUB_DELETE_AN_EMAIL_ADDRESS_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: properties.emails.items: properties | `` |
| `GITHUB_DELETE_SOCIAL_ACCOUNTS_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: properties.account_urls.items: properties | `` |
| `GITHUB_EMO_J_IS_GET` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_ENABLE_GITHUB_ACTIONS_IN_SELECTED_REPOSITORIES` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_ENCRYPT_ORG_DEV_ENV_SECRET` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_GET_ALL_API_VERSIONS` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_ALL_CODES_OF_CONDUCT` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_ALL_GITIGNORE_TEMPLATES` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_EMOJIS` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_FEEDS` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_GITHUB_META_INFORMATION` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_INTERACTION_RESTRICTIONS_FOR_YOUR_PUBLIC_REPOSITORIES` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_PUBLIC_KEY_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_RATE_LIMIT_STATUS_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GET_THE_ZEN_OF_GITHUB` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GIST_S_CREATE` | `openai_strict` | ValueError: strict-unsupported: properties.files.additionalProperties: additionalProperties; propert | `` |
| `GITHUB_GITHUB_API_ROOT` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_GITHUB_SET_REPO_RUNNER_LABELS` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_ISSUES_CREATE` | `openai_strict` | ValueError: strict-unsupported: properties.assignees.items: properties; properties.labels.items: pro | `` |
| `GITHUB_LIST_GLOBAL_SECURITY_ADVISORIES` | `openai_strict` | ValueError: strict-unsupported: properties.affects.items: properties; properties.cwes.items: propert | `` |
| `GITHUB_LIST_ORG_RESOURCES_WITH_PERSONAL_TOKENS` | `openai_strict` | ValueError: strict-unsupported: properties.owner.items: properties | `` |
| `GITHUB_LIST_ORG_RESOURCE_ACCESS_TOKENS` | `openai_strict` | ValueError: strict-unsupported: properties.owner.items: properties | `` |
| `GITHUB_MANAGE_ACCESS_CONTROL_FOR_ORGANIZATION_CODESPACES` | `openai_strict` | ValueError: strict-unsupported: properties.selected_usernames.items: properties | `` |
| `GITHUB_MANAGE_CUSTOM_PROPERTIES_FOR_ORG_REPOS` | `openai_strict` | ValueError: strict-unsupported: properties.properties.items: additionalProperties; properties.reposi | `` |
| `GITHUB_META_ROOT` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_PRIVATELY_REPORT_A_SECURITY_VULNERABILITY` | `openai_strict` | ValueError: strict-unsupported: properties.cwe_ids.items: properties; properties.vulnerabilities.ite | `` |
| `GITHUB_REMOVE_ASSIGNEES_FROM_AN_ISSUE` | `openai_strict` | ValueError: strict-unsupported: properties.assignees.items: properties | `` |
| `GITHUB_REMOVE_INTERACTION_RESTRICTIONS_FROM_YOUR_PUBLIC_REPOSITORIES` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_REMOVE_REQUESTED_REVIEWERS_FROM_A_PULL_REQUEST` | `openai_strict` | ValueError: strict-unsupported: properties.reviewers.items: properties; properties.team_reviewers.it | `` |
| `GITHUB_REMOVE_USERS_FROM_CODESPACES_ACCESS_FOR_AN_ORGANIZATION` | `openai_strict` | ValueError: strict-unsupported: properties.selected_usernames.items: properties | `` |
| `GITHUB_REPLACE_ALL_REPOSITORY_TOPICS` | `openai_strict` | ValueError: strict-unsupported: properties.names.items: properties | `` |
| `GITHUB_REPLACE_ORG_SECRET_VISIBILITY_TO_SELECTED` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_REPLACE_REPO_ACCESS_ON_ORG_DEV_ENV_SECRET_SET` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_REPO_S_CREATE_IN_ORG` | `openai_strict` | ValueError: strict-unsupported: properties.custom_properties: additionalProperties | `` |
| `GITHUB_REQUEST_REVIEWERS_FOR_A_PULL_REQUEST` | `openai_strict` | ValueError: strict-unsupported: properties.reviewers.items: properties; properties.team_reviewers.it | `` |
| `GITHUB_REVIEW_PENDING_DEPLOYMENTS_FOR_A_WORKFLOW_RUN` | `openai_strict` | ValueError: strict-unsupported: properties.environment_ids.items: properties | `` |
| `GITHUB_REVIEW_RESOURCE_REQUESTS_WITH_FINE_GRAINED_TOKENS` | `openai_strict` | ValueError: strict-unsupported: properties.pat_request_ids.items: properties | `` |
| `GITHUB_REVOKE_AN_INSTALLATION_ACCESS_TOKEN` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GITHUB_SECURITY_ADVISORIES_LIST_GLOBAL_ADVISORIES` | `openai_strict` | ValueError: strict-unsupported: properties.affects.items: properties; properties.cwes.items: propert | `` |
| `GITHUB_SET_LABELS_FOR_AN_ISSUE` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_SET_ORG_ALLOWED_ACTIONS` | `openai_strict` | ValueError: strict-unsupported: properties.patterns_allowed.items: properties | `` |
| `GITHUB_SET_ORG_RUNNER_LABELS` | `openai_strict` | ValueError: strict-unsupported: properties.labels.items: properties | `` |
| `GITHUB_SET_REPO_ALLOWED_ACTIONS` | `openai_strict` | ValueError: strict-unsupported: properties.patterns_allowed.items: properties | `` |
| `GITHUB_SET_SELECTED_REPOSITORIES_FOR_AN_ORGANIZATION_SECRET` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_SET_SELECTED_REPOSITORIES_FOR_AN_ORGANIZATION_VARIABLE` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_SET_SELECTED_REPOSITORIES_FOR_A_USER_SECRET` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_SET_STATUS_CHECK_CONTEXTS` | `openai_strict` | ValueError: strict-unsupported: properties.contexts.items: properties | `` |
| `GITHUB_TRANSFER_A_REPOSITORY` | `openai_strict` | ValueError: strict-unsupported: properties.team_ids.items: properties | `` |
| `GITHUB_UPDATE_AN_ISSUE` | `openai_strict` | ValueError: strict-unsupported: properties.assignees.items: properties; properties.labels.items: pro | `` |
| `GITHUB_UPDATE_AN_ORGANIZATION_VARIABLE` | `openai_strict` | ValueError: strict-unsupported: properties.selected_repository_ids.items: properties | `` |
| `GITHUB_UPDATE_AN_ORGANIZATION_WEBHOOK` | `openai_strict` | ValueError: strict-unsupported: properties.events.items: properties | `` |
| `GITHUB_UPDATE_A_CHECK_RUN` | `openai_strict` | ValueError: strict-unsupported: properties.actions.items: additionalProperties; properties.output__a | `` |
| `GITHUB_UPDATE_A_CODESPACE_FOR_THE_AUTHENTICATED_USER` | `openai_strict` | ValueError: strict-unsupported: properties.recent_folders.items: properties | `` |
| `GITHUB_UPDATE_A_CODE_SCANNING_DEFAULT_SETUP_CONFIGURATION` | `openai_strict` | ValueError: strict-unsupported: properties.languages.items: properties | `` |
| `GITHUB_UPDATE_A_CUSTOM_ORGANIZATION_ROLE` | `openai_strict` | ValueError: strict-unsupported: properties.permissions.items: properties | `` |
| `GITHUB_UPDATE_A_GIST` | `openai_strict` | ValueError: strict-unsupported: properties.files.additionalProperties: additionalProperties; propert | `` |
| `GITHUB_UPDATE_A_REPOSITORY_RULESET` | `openai_strict` | ValueError: strict-unsupported: properties.bypass_actors.items: additionalProperties; properties.con | `` |
| `GITHUB_UPDATE_A_REPOSITORY_WEBHOOK` | `openai_strict` | ValueError: strict-unsupported: properties.add_events.items: properties; properties.events.items: pr | `` |
| `GITHUB_UPDATE_BRANCH_PROTECTION` | `openai_strict` | ValueError: strict-unsupported: properties.required__pull__request__reviews__bypass__pull__request__ | `` |
| `GITHUB_UPDATE_PULL_REQUEST_REVIEW_PROTECTION` | `openai_strict` | ValueError: strict-unsupported: properties.bypass__pull__request__allowances__apps.items: properties | `` |
| `GITHUB_UPDATE_REPOSITORY_PREFERENCES_FOR_CHECK_SUITES` | `openai_strict` | ValueError: strict-unsupported: properties.auto_trigger_checks.items: additionalProperties | `` |
| `GITHUB_UPDATE_RESOURCE_ACCESS_WITH_TOKENS` | `openai_strict` | ValueError: strict-unsupported: properties.pat_ids.items: properties | `` |
| `GITHUB_UPDATE_STATUS_CHECK_PROTECTION` | `openai_strict` | ValueError: strict-unsupported: properties.checks.items: additionalProperties; properties.contexts.i | `` |
| `GITHUB_USERS_GET_AUTHENTICATED` | `openai_strict` | ValueError: strict-unsupported: : properties | `` |
| `GOOGLEDRIVE_CREATE_FILE` | `openai_strict` | ValueError: strict-unsupported: properties.parents.items: properties | `` |
| `GOOGLEDRIVE_FILES_MODIFY_LABELS` | `openai_strict` | ValueError: strict-unsupported: properties.label_modifications.items.properties.field_modifications. | `` |
| `GOOGLEDRIVE_STOP_WATCH_CHANNEL` | `openai_strict` | ValueError: strict-unsupported: properties.params: additionalProperties | `` |
| `GOOGLEDRIVE_WATCH_CHANGES` | `openai_strict` | ValueError: strict-unsupported: properties.params.properties.additional_properties: additionalProper | `` |
| `GOOGLE_ANALYTICS_CREATE_EXPANDED_DATA_SET` | `openai_strict` | ValueError: strict-unsupported: properties.expandedDataSet.properties.dimensionNames.items: properti | `` |
| `GOOGLE_CLASSROOM_COURSES_ANNOUNCEMENTS_CREATE` | `openai_strict` | ValueError: strict-unsupported: properties.individualStudentsOptions.properties.studentIds.items: pr | `` |
| `GOOGLE_CLASSROOM_COURSES_ANNOUNCEMENTS_PATCH` | `openai_strict` | ValueError: strict-unsupported: properties.individualStudentsOptions.properties.studentIds.items: pr | `` |
| `GOOGLE_CLASSROOM_COURSES_LIST` | `openai_strict` | ValueError: strict-unsupported: properties.courseStates.items: properties | `` |
| `GOOGLE_CLASSROOM_COURSE_WORK_CREATE` | `openai_strict` | ValueError: strict-unsupported: properties.assignment: additionalProperties; properties.materials.it | `` |
| `GOOGLE_CLASSROOM_COURSE_WORK_LIST` | `openai_strict` | ValueError: strict-unsupported: properties.courseWorkStates.items: properties | `` |
| `GOOGLE_CLASSROOM_COURSE_WORK_MATERIALS_CREATE` | `openai_strict` | ValueError: strict-unsupported: properties.individualStudentsOptions.properties.studentIds.items: pr | `` |
| `GOOGLE_CLASSROOM_COURSE_WORK_STUDENT_SUBMISSIONS_LIST` | `openai_strict` | ValueError: strict-unsupported: properties.states.items: properties | `` |
| `GOOGLE_MAPS_GEOCODING_API` | `openai_strict` | ValueError: strict-unsupported: properties.extra_computations.items: properties | `` |
| `GOOGLE_MAPS_NEARBY_SEARCH` | `openai_strict` | ValueError: strict-unsupported: properties.excludedTypes.items: properties; properties.includedTypes | `` |

## Metadata lint
Total findings: **329**

| Rule | Count |
|---|---|
| `missing-action-hint` | 227 |
| `duplicate-display-name-in-toolkit` | 82 |
| `destructive-verb-without-destructive-hint` | 12 |
| `description-repeats-name` | 8 |

### Examples
- **description-repeats-name** (warning): `GITHUB_GET_AN_ENVIRONMENT`, `GITHUB_GET_AN_ENVIRONMENT_SECRET`, `GITHUB_GET_AN_ENVIRONMENT_VARIABLE`
- **missing-action-hint** (warning): `GITHUB_CONFIGURE_JITRUNNER_FOR_ORG`, `GITHUB_CREATE_AN_AUTOLINK_REFERENCE_FOR_A_REPOSITORY`, `GITHUB_CREATE_AN_ENVIRONMENT_VARIABLE`
- **destructive-verb-without-destructive-hint** (info): `GITHUB_DISABLE_A_WORKFLOW`, `GITHUB_DISABLE_REPOSITORY_ACTIONS_IN_ORG`, `GITHUB_FORCE_CANCEL_A_WORKFLOW_RUN`
- **duplicate-display-name-in-toolkit** (info): `GITHUB_ACTIVITY_LIST_REPO_S_STARRED_BY_AUTHENTICATED_USER`, `GITHUB_ACTIVITY_LIST_STARGAZERS_FOR_REPO`, `GITHUB_ACTIVITY_STAR_REPO_FOR_AUTHENTICATED_USER`

## Limitations
- Offline only: results reflect the installed adapter versions; no live API/LLM calls.
- One failing tool does not stop the run; adapter errors are reported per tool.
- Input is the upstream CLI test mock (GitHub-heavy, ~930 tools). Counts are fixture statistics, NOT live-catalog rates.
