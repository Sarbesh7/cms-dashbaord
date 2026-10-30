# Backend–Frontend Integration Roadmap & Action Plan

This document serves as the implementation checklist, progress tracker, and technical guide for resolving all backend-to-frontend integration defects, contract divergences, and missing workflows in the CSITABMC dashboard.

*(A twin copy of this document is maintained at `dashboard/INTEGRATION_ROADMAP.md`)*

---

## 📋 Integration Status Tracker

> **Tracking Rule for Developers & AI Agents:**
> Whenever you implement or fix any item in this roadmap:
> 1. Complete the implementation and run the task's **Verification & Acceptance Criteria**.
> 2. Mark the sub-task checkboxes `[x]`.
> 3. Change the task header from `### [ ]` to `### [x]`.
> 4. Update the corresponding row in this table from `[ ] Pending` to `[x] Fixed`.
> 5. Keep both copies (`dashboard/INTEGRATION_ROADMAP.md` and `cms-dashbaord/INTEGRATION_ROADMAP.md`) in sync.

| Task ID | Feature Area | Priority | Status | Verification Focus |
| :--- | :--- | :--- | :--- | :--- |
| **INT-01** | Tenure Memberships | **P0** | [x] Fixed | Fix `member_id` / `designation` payload keys & `id` in update mutation |
| **INT-02** | Alumni Directory | **P0** | [x] Fixed | Prevent `instance.tenures.set([])` wipeout when editing alumnus without tenures |
| **INT-04** | Tenure Management | **P0** | [x] Fixed | Add `"signature"` to `TenureSerializer.Meta.fields` to persist uploads |
| **INT-05** | Core Media Serving | **P0** | [x] Fixed | Add static media route in `config/urls.py` for local dev uploads |
| **INT-03** | Auth / Profile | **P1** | [ ] Pending | Fix `ProfileSheet.jsx` router ReferenceError & implement Change Password |
| **INT-06** | Dashboard Stats | **P1** | [x] Fixed | Build backend aggregate stats endpoint & wire `useDashboard.js` |
| **INT-07** | Certificate Templates | **P2** | [ ] Pending | Integrate frontend UI with existing `/api/v1/certificates/templates/` CRUD |
| **INT-08** | Past Papers | **P2** | [x] Fixed | Move subject code map to `Constants/PastPaperSubjects.js`, add Old Course toggle & search by title |
| **INT-09** | Event Tenure Selector | **P2** | [ ] Pending | Add Tenure select dropdown to Event form and link events to tenures |
| **INT-10** | Mentor Member Link | **P3** | [ ] Pending | Add optional internal Member combobox & expose linked events summary |
| **INT-11** | Notice Slug Collision | **P3** | [ ] Pending | Add counter loop in `Notice.save()` matching Member and Event logic |
| **INT-12** | Test Automation | **P3** | [ ] Pending | Establish baseline unit and contract tests in backend and frontend |

---

## 🔄 Workflow & Verification Instructions

### How to Check and Mark Progress
1. **Identify the Task:** Pick the next pending task according to the Phase order below.
2. **Execute Changes:** Apply the code changes described in the **Action Steps**.
3. **Verify Fix:** Run the **Verification & Acceptance Criteria** steps:
   - Run tests or trigger the exact API call / UI workflow.
   - Confirm in the browser console / network tab that no 400/404/500 errors occur.
   - Confirm database records and relationships persist correctly.
4. **Mark as Done:**
   - Change `### [ ] Task INT-XX` to `### [x] Task INT-XX`.
   - Check off all sub-items under the task (`- [x]`).
   - Update the table above to `[x] Fixed`.

---

## Phase 1: Critical Contract Parity & Data Safety (Priority: P0)

### [x] Task INT-01: Correct Tenure Membership Assignment Contract
- **Problem:**
  1. `TenureAssignmentModalContent.handleSubmitWithStatus` sends `{ memberId, post }`, but `TenureMembershipSerializer` expects `{ member_id, designation }`.
  2. The update mutation call passes `{ membershipId, data }`, but `useUpdateMembership` in `useMembers.js` expects `{ id, data }`, resulting in `PUT /api/v1/memberships/undefined/`.
- **Files Involved:**
  - Frontend: `dashboard/src/app/(main)/tenure/[slug]/_components/TenureAssignmentModal.jsx`
  - Frontend: `dashboard/src/hooks/useMembers.js`
  - Backend: `cms-dashbaord/apps/tenure/serializers.py`
- **Action Steps:**
  1. In `TenureAssignmentModal.jsx` (approx. line 115), update the payload mapping:
     ```javascript
     const payload = {
       member_id: submitData.memberId,
       tenure: tenure.slug,
       designation: submitData.designation.trim(),
       role_type: submitData.role_type,
       order: Number(submitData.order),
       status: targetStatus,
     };
     ```
  2. In `TenureAssignmentModal.jsx` (approx. line 127), fix the argument passed to `updateMembershipMutation`:
     ```javascript
     const membershipId = initialData.membershipId || initialData.id;
     await updateMembershipMutation.mutateAsync({
       id: membershipId,
       membershipId,
       data: payload,
     });
     ```
  3. In `useMembers.js`, make `useUpdateMembership` resilient by accepting either `id` or `membershipId`:
     ```javascript
     mutationFn: createThrottle(async ({ id, membershipId, data }) => {
       const targetId = id || membershipId;
       const response = await apiClient.put(`/memberships/${targetId}/`, data);
       return response.data;
     }),
     ```
- **Verification & Acceptance Criteria:**
  - [x] **Implementation:** `TenureAssignmentModal.jsx` outputs `member_id` and `designation`.
  - [x] **Create Verification:** Assigning a member to a tenure submits `POST /api/v1/memberships/` and succeeds with 201 Created.
  - [x] **Update Verification:** Editing an existing assignment dispatches `PUT /api/v1/memberships/<valid_id>/` (never `/undefined/`) and succeeds with 200 OK.
  - [x] **UI State:** The tenure member table updates immediately without requiring a full page refresh.

---

### [x] Task INT-02: Prevent Accidental Alumni Tenure Deletion
- **Problem:** When an existing alumnus is edited via `AlumniForm.jsx`, no `tenureIds` are gathered. `AlumniPageContent.jsx` defaults `tenure_ids: formData.tenureIds || []`, which sends `[]` to `AlumniSerializer.update()`, triggering `instance.tenures.set([])` and wiping all linked tenure histories.
- **Files Involved:**
  - Frontend: `dashboard/src/app/(main)/alumni/_components/AlumniPageContent.jsx`
  - Backend: `cms-dashbaord/apps/tenure/serializers.py`
- **Action Steps:**
  1. In `AlumniPageContent.jsx` (approx. line 124):
     ```javascript
     const payload = {
       member_id: formData.memberId,
       graduation_year: formData.graduationYear,
       bio: formData.bio || "",
     };
     // Only supply tenure_ids if explicitly defined in the form state
     if (Array.isArray(formData.tenureIds) && formData.tenureIds.length > 0) {
       payload.tenure_ids = formData.tenureIds;
     }
     ```
  2. In `AlumniSerializer.update()` (`cms-dashbaord/apps/tenure/serializers.py`):
     ```python
     def update(self, instance, validated_data):
         # Only update M2M tenures if tenure_ids was explicitly passed in request
         has_tenure_ids = "tenures" in validated_data
         tenures = validated_data.pop("tenures", None)
         instance = super().update(instance, validated_data)
         if has_tenure_ids and tenures is not None:
             instance.tenures.set(tenures)
         return instance
     ```
- **Verification & Acceptance Criteria:**
  - [x] **Implementation:** `AlumniPageContent.jsx` omits `tenure_ids` from payload unless `formData.tenureIds` is provided.
  - [x] **Backend Safety:** `AlumniSerializer.update()` leaves existing `instance.tenures` untouched when `tenure_ids` key is absent from request.
  - [x] **Regression Check:** Edit an alumnus with existing tenure memberships in the database; verify in Django admin or via `GET /api/v1/alumni/<id>/` that linked tenures remain intact.

---

### [x] Task INT-04: Persist President Signature in TenureSerializer
- **Problem:** The frontend `TenureFormModal.jsx` allows uploading a signature image and appends it to `FormData`, but `TenureSerializer` on the backend omits `"signature"` from its `Meta.fields`. Django drops the signature silently without saving.
- **Files Involved:**
  - Backend: `cms-dashbaord/apps/tenure/serializers.py`
- **Action Steps:**
  1. Update `TenureSerializer` in `cms-dashbaord/apps/tenure/serializers.py`:
     ```python
     class TenureSerializer(serializers.ModelSerializer):
         class Meta:
             model = models.Tenure
             fields = ["id", "name", "start_date", "end_date", "slug", "signature"]
             read_only_fields = ["slug"]
     ```
- **Verification & Acceptance Criteria:**
  - [x] **Implementation:** `"signature"` added to `TenureSerializer.Meta.fields`.
  - [x] **Create Verification:** Create a new tenure with an uploaded signature image; verify the signature URL is returned in the 201 response.
  - [x] **Persistence Check:** Re-fetch `/api/v1/tenures/<slug>/` and verify `signature` points to the stored image path.

---

### [x] Task INT-05: Configure Local Media Serving in Django
- **Problem:** During development (`USE_CLOUDINARY=False`), files are saved to `cms-dashbaord/media/`, but `config/urls.py` lacks static media url patterns. Requests to `http://localhost:8000/media/*` result in HTTP 404.
- **Files Involved:**
  - Backend: `cms-dashbaord/config/urls.py`
- **Action Steps:**
  1. In `cms-dashbaord/config/urls.py`, import `settings` and `static`:
     ```python
     from django.conf import settings
     from django.conf.urls.static import static

     urlpatterns = [
         path('admin/', admin.site.urls),
         path('', TemplateView.as_view(template_name='dashboard/index.html'), name='home'),
         path('', include('apps.users.urls')),
         path('', include('apps.notices.urls')),
         path('', include('apps.events.urls')),
         path('', include('apps.tenure.urls')),
         path('', include('apps.certificates.urls')),
         path('', include('apps.papers.urls')),
     ]

     if settings.DEBUG:
         urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
     ```
- **Verification & Acceptance Criteria:**
  - [x] **Implementation:** Static media routing included under `if settings.DEBUG:`.
  - [x] **Runtime Verification:** Upload an avatar or notice image, open its `/media/...` URL in the browser, and verify it returns HTTP 200 with the image binary.

---

## Phase 2: Authentication & Core System Parity (Priority: P1)

### [ ] Task INT-03: Implement Change Password Workflow & Fix ProfileSheet
- **Problem:**
  - In `ProfileSheet.jsx`, clicking "Change Password" calls `router.push("/settings")`, but `router` is never initialized (fatal `ReferenceError: router is not defined`), and no `/settings` page exists.
  - The backend endpoint `POST /api/v1/users/change-password/` is ready but unused.
- **Files Involved:**
  - Frontend: `dashboard/src/components/common/ProfileSheet.jsx`
  - Frontend: `dashboard/src/hooks/useAuth.js`
  - Frontend: Create `dashboard/src/components/common/ChangePasswordModal.jsx`
- **Action Steps:**
  1. In `useAuth.js`, add `useChangePassword`:
     ```javascript
     export const useChangePassword = () => {
       return useMutation({
         mutationFn: async ({ old_password, new_password }) => {
           const { data } = await apiClient.post("/users/change-password/", {
             old_password,
             new_password,
           });
           return data;
         },
       });
     };
     ```
  2. Build `ChangePasswordModal.jsx` with old password, new password, and confirm new password fields with Zod validation.
  3. Wire the modal trigger into `ProfileSheet.jsx` (remove broken `router.push("/settings")`).
- **Verification & Acceptance Criteria:**
  - [ ] **Implementation:** `ProfileSheet.jsx` has no undefined `router` references.
  - [ ] **Modal Interaction:** Clicking "Change Password" in header profile dropdown opens `ChangePasswordModal`.
  - [ ] **Validation:** Entering an incorrect old password or mismatched new passwords shows clear validation feedback.
  - [ ] **End-to-End Success:** Submitting valid credentials succeeds, displays a success toast, and allows logging in with the new password.

---

### [x] Task INT-06: Implement Dedicated Dashboard Statistics Endpoint
- **Problem:** `useDashboard.js` requests full entity lists for notices, events, mentors, and certificates, computing counts client-side over only the first page of results. Completed certificate count evaluates to 0 because response is an object, not an array.
- **Files Involved:**
  - Backend: `cms-dashbaord/apps/core/views.py`, `cms-dashbaord/apps/core/urls.py`
  - Frontend: `dashboard/src/hooks/useDashboard.js`
- **Action Steps:**
  1. In `cms-dashbaord/apps/core/views.py`, create `DashboardStatsView`:
     ```python
     from rest_framework.views import APIView
     from rest_framework.response import Response
     from rest_framework.permissions import IsAuthenticatedOrReadOnly
     from apps.notices.models import Notice
     from apps.events.models import Event, Mentor
     from apps.certificates.models import Certificate
     from django.db.models import Q

     class DashboardStatsView(APIView):
         permission_classes = [IsAuthenticatedOrReadOnly]

         def get(self, request):
             published_notices = Notice.objects.filter(status__iexact="published").count()
             open_events = Event.objects.filter(
                 Q(status__iexact="published") | Q(status__iexact="open")
             ).count()
             total_mentors = Mentor.objects.count()
             completed_certificates = Certificate.objects.filter(is_project_completed=True).count()

             return Response({
                 "published_notices": published_notices,
                 "open_events": open_events,
                 "total_mentors": total_mentors,
                 "completed_certificates": completed_certificates,
                 "publishedNoticesCount": published_notices,
                 "openEventsCount": open_events,
                 "totalMentorsCount": total_mentors,
                 "certificatesIssuedCount": completed_certificates,
             })
     ```
  2. Expose `path('api/v1/dashboard/stats/', DashboardStatsView.as_view())` in `apps/core/urls.py`.
  3. Update `dashboard/src/hooks/useDashboard.js` to query `/dashboard/stats/` directly.
- **Verification & Acceptance Criteria:**
  - [x] **Backend Endpoint:** `GET /api/v1/dashboard/stats/` returns accurate database counts.
  - [x] **Frontend Accuracy:** Dashboard metric cards render correct non-zero numbers regardless of list page sizes.
  - [x] **Network Efficiency:** Replaces 4 parallel list requests with 1 single stats request.

---

## Phase 3: Secondary Features & Search Alignment (Priority: P2)

### [ ] Task INT-07: Integrate Certificate Templates UI
- **Problem:** `CertificateTemplate` has full CRUD endpoints in DRF (`/api/v1/certificates/templates/`), but the frontend has zero templates UI.
- **Files Involved:**
  - Frontend: `dashboard/src/hooks/useCertificates.js`
  - Frontend: `dashboard/src/app/(main)/certificates/`
- **Action Steps:**
  1. In `useCertificates.js`, add `useCertificateTemplates`, `useCreateCertificateTemplate`, `useDeleteCertificateTemplate`.
  2. Add a "Templates" tab or modal in `/certificates` to view existing SVG/HTML/PDF templates and upload new ones.
- **Verification & Acceptance Criteria:**
  - [ ] **Hooks Created:** `useCertificateTemplates` connected to `/api/v1/certificates/templates/`.
  - [ ] **UI Connected:** User can view templates list and upload a template file.
  - [ ] **Persistence:** Uploaded templates appear in list and can be deleted.

---

### [x] Task INT-08: Fix Past Papers Subject Search, Display, Old Course Toggle & Constants Extraction
- **Problem:**
  - Subject code map was hardcoded inside `usePastPapers.js`, making it difficult to update when BSc CSIT curriculum codes change.
  - Papers lacked an "Old Course" flag to distinguish older syllabus papers (e.g., CSC419 Java vs CSC425 Java) and preserve past paper records without missing data.
  - Backend filtering only matched raw subject code strings, yielding 0 results when searching by human-readable subject name like "Programming".
- **Files Involved:**
  - Frontend: `dashboard/src/lib/Constants/PastPaperSubjects.js`
  - Frontend: `dashboard/src/hooks/usePastPapers.js`
  - Frontend: `dashboard/src/lib/Schema/pastPaperSchema.js`
  - Frontend: `dashboard/src/app/(main)/past-papers/_components/pastPaperFormModel.jsx`
  - Frontend: `dashboard/src/app/(main)/past-papers/_components/PastPapersPageContent.jsx`
  - Frontend: `dashboard/src/app/(main)/past-papers/_components/pastPaperTable.jsx`
  - Backend: `cms-dashbaord/apps/papers/models.py`
  - Backend: `cms-dashbaord/apps/papers/serializers.py`
  - Backend: `cms-dashbaord/apps/papers/views.py`
  - Backend: `cms-dashbaord/apps/papers/migrations/0005_alter_pastpaper_unique_together_and_more.py`
- **Action Steps & Implementation:**
  1. Extracted subject code mapping into `dashboard/src/lib/Constants/PastPaperSubjects.js` with documented guide for updating directly on GitHub.
  2. Added `is_old_course = models.BooleanField(default=False)` in `PastPaper` model, expanded `max_length=20`, and updated `unique_together` to include `model_set` and `is_old_course`.
  3. Ran Django migration `0005_alter_pastpaper_unique_together_and_more`.
  4. Added dynamic `subject_name = serializers.CharField(max_length=20)` to `PastPaperSerializer`.
  5. Enhanced `PastPaperListView.get()` to search across both course codes and titles via `Q` objects, and added `is_old_course` filtering.
  6. Added Old Course radio toggle in `pastPaperFormModel.jsx`, support for custom unmapped codes, and rendered an amber `[Old Course]` badge in the table and preview modal.
- **Verification & Acceptance Criteria:**
  - [x] **Constants Extracted:** `dashboard/src/lib/Constants/PastPaperSubjects.js` created and imported into hooks and forms.
  - [x] **Old Course Toggle:** Form allows selecting "Old Course (Legacy)", passes `is_old_course` to backend, and table renders `Old Course` tag.
  - [x] **Subject Code Update Safety:** Updating a subject code or toggling old course updates slug safely and avoids unique collision errors.
  - [x] **Search by Title & Code:** Querying `?search=programming` or `?search=CSC114` matches correctly via backend Q-search.

---

### [x] Task INT-09: Connect Events to Tenure Hierarchy
- **Problem:** The `Event` model has `tenure = models.ForeignKey(Tenure, null=True, blank=True)`, but `EventForm.jsx` does not include a tenure picker. Events are never associated with a tenure in the dashboard.
- **Files Involved:**
  - Frontend: `dashboard/src/app/(main)/events/_components/EventForm.jsx`
  - Frontend: `dashboard/src/app/(main)/events/_components/EventsPageContent.jsx`
- **Action Steps:**
  1. Fetch tenures in `EventsPageContent.jsx` via `useTenures()`.
  2. Add a Tenure dropdown to `EventForm.jsx`.
  3. Append `tenure` (ID) in `EventsPageContent.jsx::handleFormSubmitSuccess`.
- **Verification & Acceptance Criteria:**
  - [x] **Form Control:** Event creation and edit forms present a Tenure selector.
  - [x] **Persistence:** Saving an event stores the foreign key relation, and `tenure_name` appears in the event list table.

---

## Phase 4: Enhancements, Reliability & Automation (Priority: P3)

### [ ] Task INT-10: Connect Mentor Internal Member Selection
- **Problem:** `Mentor` has `member = models.ForeignKey(Member, null=True, blank=True)`. The frontend only captures name/socials, preventing linking a mentor to an existing member profile.
- **Files Involved:**
  - Frontend: `dashboard/src/app/(main)/mentors/_components/MentorForm.jsx`
  - Backend: `cms-dashbaord/apps/events/serializers.py`
- **Action Steps:**
  1. In `MentorForm.jsx`, provide an optional Combobox to select an internal Member.
  2. In `MentorSerializer`, expose the reverse relationship for linked `events`.
- **Verification & Acceptance Criteria:**
  - [ ] **Combobox:** Selecting an existing Member auto-fills mentor name and image.
  - [ ] **Persistence:** `member` foreign key is saved and `is_internal_member` returns `true`.

---

### [ ] Task INT-11: Add Notice Slug Collision Retry Loop
- **Problem:** Unlike `Member` and `Event`, `Notice.save()` does not have a uniqueness retry loop. Two notices with the same title cause a database `IntegrityError`.
- **Files Involved:**
  - Backend: `cms-dashbaord/apps/notices/models.py`
- **Action Steps:**
  1. Update `Notice.save()`:
     ```python
     def save(self, *args, **kwargs):
         if not self.slug:
             base_slug = slugify(self.title)
             slug = base_slug
             counter = 1
             while Notice.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                 slug = f"{base_slug}-{counter}"
                 counter += 1
             self.slug = slug
         super().save(*args, **kwargs)
     ```
- **Verification & Acceptance Criteria:**
  - [ ] **Collision Test:** Create two notices with the exact same title; verify the second gets `-1` suffix instead of raising a 500 database error.

---

### [ ] Task INT-12: Establish Integration Test Harness
- **Problem:** 0 backend tests and 0 frontend tests currently exist across both repositories.
- **Action Steps:**
  1. In `cms-dashbaord/apps/tenure/tests.py`, implement test cases for:
     - `test_create_tenure_membership_payload()`
     - `test_update_alumni_preserves_tenures()`
     - `test_tenure_signature_upload()`
  2. In `dashboard/`, configure Vitest / React Testing Library to test `axios` refresh interceptor and form submit payloads.
- **Verification & Acceptance Criteria:**
  - [ ] **Backend Tests:** `python manage.py test` passes with green results.
  - [ ] **Frontend Tests:** `npm test` runs and passes.
