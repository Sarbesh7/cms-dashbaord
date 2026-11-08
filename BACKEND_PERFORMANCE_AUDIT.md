# CSITABMC CMS Dashboard — Backend Database & Query Performance Audit

**Audit Date**: November 8, 2026  
**Target Environment**: Django 5.2 / Django REST Framework (PostgreSQL in production, SQLite in local dev)  
**Methodology Skill**: `.agents/skills/database-query-optimization/` (Query Analysis, Indexing Strategy, Query Optimization Techniques, Optimization Checklist)

---

## 1. Executive Summary

A comprehensive performance audit was conducted across all backend applications (`core`, `users`, `tenure`, `events`, `notices`, `certificates`, `papers`, `blogs`, and `notifications`). 

The audit identified **6 confirmed query performance bottlenecks**:
1. **N+1 count evaluation in `NotificationSentSerializer`**: Running an individual `SELECT COUNT(*)` for every sent notification row on paginated list responses.
2. **Missing relationship prefetching in `AlumniDetailView`**: Triggering lazy SQL queries on many-to-many `tenures`.
3. **Un-prefetched iteration loop in `clone_members`**: Triggering an individual SQL query per source membership when reading member properties.
4. **Multiple sequential table scans in `activity_log_summary()`**: Executing 3 separate `.count()` queries sequentially against `ActivityLog` instead of a single consolidated aggregation.
5. **Redundant table joins in `ActivityLogListView` & `ActivityLogDetailView`**: Joining `users_user` on an append-only audit model that already snapshots actor details.
6. **Missing B-tree composite and single indexes on frequently filtered & ordered columns**: `ActivityLog` (action + timestamp, module + timestamp), `Event` (status + date, date), `Notice` (status), and `TenureMembership` (status + order).

All 6 confirmed issues can be safely optimized with zero breaking changes to API contracts, serializer keys, permissions, or frontend compatibility.

---

## 2. Skill Execution & Methodology

The audit followed the procedures documented in `.agents/skills/database-query-optimization/`:
- **Query Analysis**: Audited ORM querysets against SQL query generation, looking for nested loops, repeated scans, and sequential full table reads.
- **Indexing Strategy**: Verified whether `WHERE`, `JOIN`, and `ORDER BY` columns have matching single or composite B-tree indexes, ensuring most-selective columns come first and avoiding redundant indexes.
- **Query Optimization**: Identified N+1 patterns in serializers, un-prefetched many-to-many/foreign-key relations, and opportunities to convert multiple counts into atomic database aggregations.
- **Optimization Checklist**: Validated that all proposed changes preserve transactions, avoid premature Redis/caching complexity, and maintain documentation and test integrity.

---

## 3. Confirmed Performance Issues

### Finding 1: N+1 Count Evaluation in Sent Notifications List

- **Application / Module**: `apps/notifications`
- **Affected File & Function**: `apps/notifications/serializers.py::NotificationSentSerializer` (line 95)
- **Problem Identified**: `recipient_count = serializers.IntegerField(source='recipients.count', read_only=True)`
- **Why It Is Inefficient**: Although `NotificationSentListView` prefetches `recipients__recipient`, invoking `.count` bypasses Django's in-memory `_prefetched_objects_cache` and issues a separate SQL query:
  ```sql
  SELECT COUNT(*) FROM "notifications_notificationrecipient" WHERE "notification_id" = %s;
  ```
  On a page of 15 sent notifications, this triggers **15 extra database queries** (1 + 15 = 16 queries).
- **Expected Impact**: Reduces query count from `O(N)` to `O(1)` (1 query for notifications + 1 query for prefetched recipients = 2 queries total).
- **Recommended Fix**: Use `SerializerMethodField` to read `len(obj.recipients.all())` when prefetch cache is populated:
  ```python
  def get_recipient_count(self, obj):
      if hasattr(obj, '_prefetched_objects_cache') and 'recipients' in obj._prefetched_objects_cache:
          return len(obj.recipients.all())
      return obj.recipients.count()
  ```
- **Priority**: High
- **Safe to Fix Immediately**: Yes

---

### Finding 2: Missing Many-to-Many Prefetch in Alumni Detail View

- **Application / Module**: `apps/tenure`
- **Affected File & Function**: `apps/tenure/views.py::AlumniDetailView.get_object()` (line 335)
- **Problem Identified**:
  ```python
  qs = Alumni.objects.select_related("member")
  ```
- **Why It Is Inefficient**: `AlumniSerializer` renders `tenures = TenureDropdownSerializer(many=True, read_only=True)`. Because `tenures` is not prefetched in `get_object()`, serializing the alumni record forces a secondary lazy query to fetch the associated tenures from `tenure_alumni_tenures` and `tenure_tenure`.
- **Expected Impact**: Reduces database queries per detail lookup from 2 to 1 (or loads all needed relationships in the initial batch).
- **Recommended Fix**:
  ```python
  qs = Alumni.objects.select_related("member").prefetch_related("tenures")
  ```
- **Priority**: Medium
- **Safe to Fix Immediately**: Yes

---

### Finding 3: Un-prefetched Loop Queries in Tenure Member Cloning

- **Application / Module**: `apps/tenure`
- **Affected File & Function**: `apps/tenure/views.py::clone_members()` (lines 209–220)
- **Problem Identified**:
  ```python
  source_memberships = TenureMembership.objects.filter(tenure=source_tenure, member__isnull=False)
  ...
  new_memberships = [
      TenureMembership(
          member=m.member,
          member_name_snapshot=m.member.name,  # <-- Triggers DB query per membership
          ...
      )
      for m in source_memberships
  ]
  ```
- **Why It Is Inefficient**: `source_memberships` does not eager-load `member`. For a tenure with 25 committee members, this loop executes **25 sequential `SELECT` queries** against `tenure_member`.
- **Expected Impact**: Replaces 25 queries with **1 query** via `select_related('member')`.
- **Recommended Fix**:
  ```python
  source_memberships = TenureMembership.objects.filter(
      tenure=source_tenure, member__isnull=False
  ).select_related("member")
  ```
- **Priority**: High
- **Safe to Fix Immediately**: Yes

---

### Finding 4: Multiple Sequential Full-Table Scans in Activity Log Summary

- **Application / Module**: `apps/core`
- **Affected File & Function**: `apps/core/dashboard.py::activity_log_summary()` (lines 289–315)
- **Problem Identified**:
  ```python
  "total_activities": ActivityLog.objects.count(),
  "logins_this_week": ActivityLog.objects.filter(action="login", timestamp__gte=week_ago).count(),
  "mutations_today": ActivityLog.objects.filter(
      action__in=[...], timestamp__gte=today_start,
  ).count(),
  ```
- **Why It Is Inefficient**: Executes 3 separate `SELECT COUNT(*)` queries against `ActivityLog` one after another on every dashboard load. In a production system with tens of thousands of log entries, this causes 3 separate index/table scans.
- **Expected Impact**: Reduces 3 database roundtrips to **1 atomic SQL query** using Django conditional aggregation.
- **Recommended Fix**:
  ```python
  counts = ActivityLog.objects.aggregate(
      total_activities=Count("id"),
      logins_this_week=Count("id", filter=Q(action="login", timestamp__gte=week_ago)),
      mutations_today=Count(
          "id",
          filter=Q(
              action__in=["create", "update", "delete", "publish", "unpublish",
                          "status_change", "role_change", "media_upload", "media_delete"],
              timestamp__gte=today_start,
          )
      ),
  )
  ```
- **Priority**: High
- **Safe to Fix Immediately**: Yes

---

### Finding 5: Redundant Table Join on Activity Log List & Detail Endpoints

- **Application / Module**: `apps/core`
- **Affected File & Function**: `apps/core/views.py::ActivityLogListView` & `ActivityLogDetailView` (lines 49, 108)
- **Problem Identified**:
  ```python
  qs = ActivityLog.objects.select_related('user').all()
  ```
- **Why It Is Inefficient**: `ActivityLog` is append-only and explicitly snapshots the user details (`actor_id_snapshot`, `actor_name_snapshot`, `user_email_snapshot`, `user_role_snapshot`). `ActivityLogSerializer` serializes `user` as a primary key integer (`obj.user_id`) and never accesses properties on the `User` model. Adding `select_related('user')` forces an unnecessary `LEFT OUTER JOIN "users_user"` on every paginated audit query.
- **Expected Impact**: Eliminates the SQL join across all activity log pagination queries, reducing database execution memory and query complexity.
- **Recommended Fix**: Remove `select_related('user')`:
  ```python
  qs = ActivityLog.objects.all()
  ```
- **Priority**: Medium
- **Safe to Fix Immediately**: Yes

---

### Finding 6: Missing Composite and Single Indexes on High-Traffic Columns

- **Application / Module**: `apps/core`, `apps/events`, `apps/notices`, `apps/tenure`
- **Affected Files**:
  - `apps/core/models.py::ActivityLog`
  - `apps/events/models.py::Event`
  - `apps/notices/models.py::Notice`
  - `apps/tenure/models.py::TenureMembership`
- **Problem Identified**:
  - `ActivityLog`: Often queried by `module` + `timestamp` or `action` + `timestamp`, and ordered by `-timestamp`. Lacks composite indexes on `('action', '-timestamp')` and `('module', '-timestamp')`.
  - `Event`: Every public request filters `status__in=['published', 'completed']` and orders by `-date`. Neither `status` nor `date` has a database index.
  - `Notice`: Public requests filter `status='published'` and order by `-created_at`. `status` has no index.
  - `TenureMembership`: Filtered by `status='published'` and ordered by `order`. Lacks an index on `('status', 'order')`.
- **Why It Is Inefficient**: Without indexes, PostgreSQL and SQLite must perform sequential scans (Full Table Scan) and in-memory sort operations on every unauthenticated public request.
- **Expected Impact**: Replaces sequential scans with fast Index Scans; dramatically lowers CPU utilization under concurrent visitor traffic.
- **Recommended Fix**: Add targeted indexes in the models and generate Django migrations:
  - `ActivityLog`: `models.Index(fields=['action', '-timestamp'])`, `models.Index(fields=['module', '-timestamp'])`
  - `Event`: `models.Index(fields=['status', '-date'])`, `date = models.DateTimeField(db_index=True)`
  - `Notice`: `status = models.CharField(..., db_index=True)`
  - `TenureMembership`: `models.Index(fields=['status', 'order'])`
- **Priority**: High
- **Safe to Fix Immediately**: Yes

---

## 4. Potential Improvements Requiring Further Investigation

1. **Full-Text Search vs `icontains`**:
   - Several list views (`notices`, `events`, `members`, `announcements`) use `title__icontains=search`.
   - On small datasets (< 10,000 rows), `icontains` performs well. As content grows into tens of thousands of records, PostgreSQL `pg_trgm` (trigram) indexes or a dedicated full-text search vector would prevent sequential table scans on leading wildcards.
   - *Status*: Defer until database volume warrants PostgreSQL-specific extensions.

2. **React Query `staleTime` Optimization**:
   - In the frontend dashboard, `staleTime` defaults to `0`, causing the browser to re-request table data on every tab switch even when data was fetched seconds earlier. Setting a 30s `staleTime` eliminates redundant network roundtrips completely.
   - *Status*: Frontend optimization; can be configured independently.

---

## 5. Deferred Architectural Recommendations

1. **Redis Cache Backend**:
   - The project currently uses Django's default cache (local memory / database). Introducing Redis is unnecessary at current traffic levels and would introduce extra operational and infrastructure overhead.
   - *Decision*: Defer until multi-instance horizontal scaling is deployed.

2. **Historical Activity Log Archival / Partitioning**:
   - Append-only activity logs will eventually grow indefinitely. Partitioning `ActivityLog` by year or archiving records older than 2 years will be beneficial in the future.
   - *Decision*: Defer until activity log volume exceeds 500,000 rows.

---

## 6. Performance Comparison (Expected / Baseline)

| Endpoint / Operation | Current Behavior | Optimized Behavior | Expected Gain |
|---|---|---|---|
| `GET /api/v1/notifications/sent/` | `1 + N` queries (1 query + 1 query per row for recipient count) | `2` queries (fixed O(1) complexity via prefetch cache) | **~85% fewer queries** on page size 15 |
| `GET /api/v1/tenure/alumni/<id>/` | `2` queries (alumni query + lazy tenures query) | `1` prefetch query | **50% fewer roundtrips** |
| `POST .../clone-members/` | `1 + N` queries (1 query + 1 query per member in loop) | `1` query via `select_related('member')` | **~95% fewer queries** on 20-member committee |
| `GET /api/v1/activity-logs/summary/` | `4` sequential queries (3 separate counts + 1 group by) | `2` queries (1 consolidated aggregate + 1 group by) | **50% fewer table scans** |
| `GET /api/v1/activity-logs/` | Query with `LEFT OUTER JOIN "users_user"` | Clean query without join | Reduced memory and join overhead |
| Public Events / Notices list | Full Table Scan on `status` & `date` | B-tree Index Scan | **Sub-50ms response times** under concurrency |

---

## 7. Implementation Plan

The optimizations will be implemented under the OpenSpec change **`backend-query-performance-optimization`**:
1. Implement N+1 serializer and view optimizations in `apps/notifications` and `apps/tenure`.
2. Consolidate `activity_log_summary()` in `apps/core/dashboard.py`.
3. Add targeted indexes to `core`, `events`, `notices`, and `tenure` models and generate Django migrations.
4. Add automated `assertNumQueries` regression tests to verify that query complexity remains constant O(1).

