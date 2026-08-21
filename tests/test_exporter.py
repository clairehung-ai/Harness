# tests/test_exporter.py
"""
Tests for harness/utils/exporter.py
Covers Issue #5: overwrite parameter behaviour
"""
import os
import pytest
from harness.utils.exporter import export_code_to_directory, create_project_structure


def test_export_code_skips_existing_when_overwrite_false(tmp_path):
    """overwrite=False（預設）時，已存在的檔案不被覆寫"""
    # 先建立一個已存在的檔案
    existing = tmp_path / "models.py"
    existing.write_text("# original content")

    export_code_to_directory(
        {"models.py": "# new content"},
        output_dir=str(tmp_path),
        overwrite=False,
    )

    assert existing.read_text() == "# original content"


def test_export_code_overwrites_when_overwrite_true(tmp_path):
    """overwrite=True 時，已存在的檔案應被覆寫"""
    existing = tmp_path / "models.py"
    existing.write_text("# original content")

    export_code_to_directory(
        {"models.py": "# new content"},
        output_dir=str(tmp_path),
        overwrite=True,
    )

    assert existing.read_text() == "# new content"


def test_export_code_creates_new_file(tmp_path):
    """無論 overwrite，新檔案都應被建立"""
    export_code_to_directory(
        {"new_file.py": "# brand new"},
        output_dir=str(tmp_path),
        overwrite=False,
    )

    assert (tmp_path / "new_file.py").read_text() == "# brand new"


def test_create_project_structure_overwrite_true(tmp_path):
    """create_project_structure(overwrite=True) 應覆寫現有檔案"""
    # 模擬現有專案
    backend_dir = tmp_path / "myproject"
    backend_dir.mkdir()
    existing = backend_dir / "models.py"
    existing.write_text("# original")

    create_project_structure(
        completed_code={"models.py": "# updated by Harness"},
        task_results=[],
        project_name=str(backend_dir),
        include_tests=False,
        overwrite=True,
    )

    assert existing.read_text() == "# updated by Harness"


def test_create_project_structure_overwrite_false(tmp_path):
    """create_project_structure(overwrite=False) 應跳過現有檔案"""
    backend_dir = tmp_path / "myproject"
    backend_dir.mkdir()
    existing = backend_dir / "models.py"
    existing.write_text("# original")

    create_project_structure(
        completed_code={"models.py": "# updated by Harness"},
        task_results=[],
        project_name=str(backend_dir),
        include_tests=False,
        overwrite=False,
    )

    assert existing.read_text() == "# original"


def test_create_project_structure_default_is_overwrite_true(tmp_path):
    """create_project_structure 預設應為 overwrite=True，確保 Harness 修改生效"""
    backend_dir = tmp_path / "myproject"
    backend_dir.mkdir()
    existing = backend_dir / "api.py"
    existing.write_text("# original api")

    create_project_structure(
        completed_code={"api.py": "# harness generated api"},
        task_results=[],
        project_name=str(backend_dir),
        include_tests=False,
    )

    # 預設應覆寫
    assert existing.read_text() == "# harness generated api"
