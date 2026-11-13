from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase
from apps.tenure.models import Tenure, Member, TenureMembership, Alumni

User = get_user_model()


class TenureIntegrationTests(APITestCase):
    def setUp(self):
        # Create an admin user for authenticated requests
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpassword123",
            role="admin",
        )
        self.client.force_authenticate(user=self.user)

        # Base test data
        self.tenure_2023 = Tenure.objects.create(
            name="Tenure 2023-2024",
            start_date="2023-01-01",
            end_date="2024-01-01",
        )
        self.tenure_2024 = Tenure.objects.create(
            name="Tenure 2024-2025",
            start_date="2024-01-01",
            end_date="2025-01-01",
        )
        self.member = Member.objects.create(
            name="John Doe",
            email="john@example.com",
            status="published",
        )

    def test_tenure_membership_creation_with_member_id_and_designation(self):
        """Verify creating a tenure membership using member_id and designation."""
        payload = {
            "member_id": self.member.id,
            "tenure": self.tenure_2024.slug,
            "role_type": "EXECUTIVE",
            "designation": "President",
            "order": 1,
            "status": "published",
        }
        response = self.client.post("/api/v1/memberships/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["designation"], "President")
        self.assertEqual(response.data["role_type"], "EXECUTIVE")
        self.assertEqual(response.data["member"]["id"], self.member.id)

        # Verify in database
        membership = TenureMembership.objects.get(id=response.data["id"])
        self.assertEqual(membership.member, self.member)
        self.assertEqual(membership.tenure, self.tenure_2024)
        self.assertEqual(membership.designation, "President")

    def test_tenure_membership_update(self):
        """Verify updating a tenure membership by PK without undefined in URL."""
        membership = TenureMembership.objects.create(
            member=self.member,
            tenure=self.tenure_2024,
            role_type="EXECUTIVE",
            designation="Secretary",
            order=2,
        )
        payload = {
            "member_id": self.member.id,
            "tenure": self.tenure_2024.slug,
            "role_type": "EXECUTIVE",
            "designation": "Vice President",
            "order": 2,
            "status": "published",
        }
        response = self.client.put(
            f"/api/v1/memberships/{membership.id}/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertEqual(membership.designation, "Vice President")

    def test_alumni_update_preserves_tenures_when_omitted(self):
        """Verify updating alumni without tenure_ids preserves existing tenure relationships."""
        alumni = Alumni.objects.create(
            member=self.member,
            graduation_year=2023,
            bio="Original bio",
        )
        alumni.tenures.add(self.tenure_2023, self.tenure_2024)
        self.assertEqual(alumni.tenures.count(), 2)

        # Update without passing tenure_ids
        payload = {
            "bio": "Updated bio text",
            "graduation_year": 2024,
        }
        response = self.client.put(
            f"/api/v1/alumni/{alumni.id}/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alumni.refresh_from_db()
        self.assertEqual(alumni.bio, "Updated bio text")
        self.assertEqual(alumni.graduation_year, 2024)
        # Ensure tenures were not wiped out
        self.assertEqual(alumni.tenures.count(), 2)
        tenure_ids = set(alumni.tenures.values_list("id", flat=True))
        self.assertEqual(tenure_ids, {self.tenure_2023.id, self.tenure_2024.id})

    def test_alumni_update_replaces_tenures_when_explicitly_passed(self):
        """Verify providing tenure_ids explicitly updates the relationship set."""
        alumni = Alumni.objects.create(
            member=self.member,
            graduation_year=2023,
            bio="Original bio",
        )
        alumni.tenures.add(self.tenure_2023, self.tenure_2024)

        # Update with only one tenure_id
        payload = {
            "tenure_ids": [self.tenure_2024.id],
        }
        response = self.client.put(
            f"/api/v1/alumni/{alumni.id}/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        alumni.refresh_from_db()
        self.assertEqual(alumni.tenures.count(), 1)
        self.assertEqual(list(alumni.tenures.values_list("id", flat=True)), [self.tenure_2024.id])

    def test_tenure_signature_field_persistence(self):
        """Verify Tenure serialization and persistence includes the signature field."""
        valid_png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?"
            b"\x00\x05\xfe\x02\xfe\r\xef\x8b\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        signature_file = SimpleUploadedFile(
            "test_signature.png",
            valid_png_bytes,
            content_type="image/png",
        )
        tenure_with_sig = Tenure.objects.create(
            name="Tenure With Sig",
            start_date="2025-01-01",
            end_date="2026-01-01",
            signature=signature_file,
        )

        # Check detail endpoint
        response = self.client.get(f"/api/v1/tenures/{tenure_with_sig.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("signature", response.data)
        self.assertIsNotNone(response.data["signature"])
        self.assertTrue(response.data["signature"].endswith(".png"))

        # Check list endpoint
        list_response = self.client.get("/api/v1/tenures/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        found = any(t.get("slug") == tenure_with_sig.slug and t.get("signature") for t in list_response.data)
        self.assertTrue(found)

    def test_tenure_numeric_slug_lookup_and_delete(self):
        """Verify that a tenure with a numeric slug (e.g. '23124') resolves by slug and deletes."""
        tenure_numeric = Tenure.objects.create(
            name="Tenure Numeric Slug",
            slug="23124",
            start_date="2027-01-01",
            end_date="2028-01-01",
        )
        # Even though tenure_numeric.id != 23124, slug lookup should resolve it
        self.assertNotEqual(tenure_numeric.id, 23124)

        # GET detail using numeric slug
        resp = self.client.get("/api/v1/tenures/23124/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["id"], tenure_numeric.id)

        # DELETE using numeric slug
        del_resp = self.client.delete("/api/v1/tenures/23124/")
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tenure.objects.filter(id=tenure_numeric.id).exists())

    def test_tenure_fallback_to_id_lookup(self):
        """Verify that if slug doesn't match, numeric string falls back to id."""
        tenure = Tenure.objects.create(
            name="Tenure Standard",
            start_date="2028-01-01",
            end_date="2029-01-01",
        )
        # Query using its numeric ID
        resp = self.client.get(f"/api/v1/tenures/{tenure.id}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["slug"], tenure.slug)

    def test_member_numeric_slug_and_role_permissions(self):
        """Verify member numeric slug resolution and that superadmin can delete whereas admin cannot."""
        member_numeric = Member.objects.create(
            name="Member Numeric",
            slug="9999",
            status="published",
        )
        self.assertNotEqual(member_numeric.id, 9999)

        # Admin tries to delete member -> should be 403 Forbidden (PROTECTED_PERMISSIONS)
        # Create a standard user with role="admin" (not is_superuser)
        admin_user = User.objects.create_user(
            username="content_admin",
            email="content_admin@example.com",
            password="adminpassword123",
            role="admin",
        )
        self.client.force_authenticate(user=admin_user)
        admin_del_resp = self.client.delete("/api/v1/members/9999/")
        self.assertEqual(admin_del_resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Member.objects.filter(id=member_numeric.id).exists())

        # Switch to superadmin
        superadmin = User.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="adminpassword123",
            role="superadmin",
        )
        self.client.force_authenticate(user=superadmin)

        # Superadmin deletes using numeric slug -> 204
        sa_del_resp = self.client.delete("/api/v1/members/9999/")
        self.assertEqual(sa_del_resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Member.objects.filter(id=member_numeric.id).exists())
