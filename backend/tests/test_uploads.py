"""Evidence and document uploads.

Evidence previously stored a client-supplied path pointing at a file that never
existed anywhere.
"""

from pathlib import Path

from app.config import settings
from tests.conftest import MANAGER, VIEWER, auth, make_record

PDF = b"%PDF-1.4\nfake pdf body\n%%EOF"


def upload_evidence(client, record_id, *, name="nachweis.pdf", content=PDF, user=MANAGER, **fields):
    return client.post(
        f"/api/compliance-records/{record_id}/evidence",
        headers=auth(user),
        files={"file": (name, content, "application/pdf")},
        data={"evidence_type": "certificate", **fields},
    )


def test_upload_stores_the_file_and_returns_metadata(client):
    record = make_record(client)
    response = upload_evidence(client, record["id"])
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["file_name"] == "nachweis.pdf"
    assert body["file_size_bytes"] == len(PDF)
    assert body["uploaded_by"] == MANAGER
    assert (Path(settings.uploads_dir) / body["storage_path"]).is_file()


def test_storage_path_is_server_generated(client):
    """A client must not be able to choose where the file lands."""
    record = make_record(client)
    body = upload_evidence(client, record["id"], name="../../etc/passwd.pdf").json()

    assert ".." not in body["storage_path"]
    assert body["storage_path"].startswith("evidence/")
    resolved = (Path(settings.uploads_dir) / body["storage_path"]).resolve()
    assert resolved.is_relative_to(Path(settings.uploads_dir).resolve())
    # The display name is sanitised too.
    assert "/" not in body["file_name"]


def test_download_returns_the_stored_bytes(client):
    record = make_record(client)
    evidence = upload_evidence(client, record["id"]).json()

    response = client.get(f"/api/evidence/{evidence['id']}/download", headers=auth(MANAGER))
    assert response.status_code == 200
    assert response.content == PDF


def test_download_requires_permission(client):
    from app import models
    from app.database import SessionLocal

    record = make_record(client)
    evidence = upload_evidence(client, record["id"]).json()

    with SessionLocal() as db:
        role = db.get(models.Role, "role-viewer")
        original = list(role.permissions)
        role.permissions = ["personnel:read"]
        db.commit()
    try:
        assert client.get(f"/api/evidence/{evidence['id']}/download", headers=auth(VIEWER)).status_code == 403
    finally:
        with SessionLocal() as db:
            db.get(models.Role, "role-viewer").permissions = original
            db.commit()


def test_rejected_file_types(client):
    record = make_record(client)
    response = client.post(
        f"/api/compliance-records/{record['id']}/evidence",
        headers=auth(MANAGER),
        files={"file": ("payload.exe", b"MZ...", "application/octet-stream")},
    )
    assert response.status_code == 415


def test_oversized_upload_is_rejected_and_leaves_nothing_behind(client, monkeypatch):
    record = make_record(client)
    monkeypatch.setattr(settings, "upload_max_bytes", 1024)

    before = set(Path(settings.uploads_dir).rglob("*.pdf"))
    response = upload_evidence(client, record["id"], content=b"x" * 5000)
    assert response.status_code == 413
    assert set(Path(settings.uploads_dir).rglob("*.pdf")) == before


def test_empty_upload_is_rejected(client):
    record = make_record(client)
    assert upload_evidence(client, record["id"], content=b"").status_code == 400


def test_deleting_evidence_removes_the_file(client):
    record = make_record(client)
    evidence = upload_evidence(client, record["id"]).json()
    path = Path(settings.uploads_dir) / evidence["storage_path"]
    assert path.is_file()

    assert client.delete(f"/api/evidence/{evidence['id']}", headers=auth(MANAGER)).status_code == 204
    assert not path.exists()


def test_deleting_the_record_removes_its_evidence_files(client):
    record = make_record(client)
    evidence = upload_evidence(client, record["id"]).json()
    path = Path(settings.uploads_dir) / evidence["storage_path"]

    client.delete(f"/api/compliance-records/{record['id']}", headers=auth(MANAGER))
    assert not path.exists()


def test_missing_file_on_disk_reports_404_not_500(client):
    record = make_record(client)
    evidence = upload_evidence(client, record["id"]).json()
    (Path(settings.uploads_dir) / evidence["storage_path"]).unlink()

    response = client.get(f"/api/evidence/{evidence['id']}/download", headers=auth(MANAGER))
    assert response.status_code == 404


def test_document_upload_and_link_to_qualification(client):
    from tests.conftest import make_employee

    document = client.post(
        "/api/documents",
        headers=auth(MANAGER),
        files={"file": ("schein.pdf", PDF, "application/pdf")},
        data={"title": "IPAF Zertifikat"},
    )
    assert document.status_code == 201, document.text
    document_id = document.json()["id"]

    employee_id = make_employee(client)
    qualification = client.post(
        "/api/employee-qualifications",
        headers=auth(MANAGER),
        json={
            "employee_id": employee_id,
            "title": "IPAF",
            "qualification_type": "training",
            "document_id": document_id,
        },
    )
    assert qualification.status_code == 200, qualification.text

    # The document is now referenced and must not vanish underneath it.
    assert client.delete(f"/api/documents/{document_id}", headers=auth(MANAGER)).status_code == 409
