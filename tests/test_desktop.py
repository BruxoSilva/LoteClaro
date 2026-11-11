import json
from pathlib import Path
import pytest
from desktop import configuration,create_desktop_app,InstanceLock,smoke_test

def test_configuration_preserves_existing_database(tmp_path):
    root=tmp_path/'user-data';(root/'data').mkdir(parents=True)
    (tmp_path/'lote-claro.json').write_text(json.dumps(dict(data_directory=str(root),port=5077,require_existing_database=True)))
    with pytest.raises(ValueError):configuration(tmp_path)
    assert not (root/'data'/'calculadora.db').exists()
    (root/'data'/'calculadora.db').write_bytes(b'preserved')
    assert configuration(tmp_path)==(root,5077)
    assert (root/'data'/'calculadora.db').read_bytes()==b'preserved'

def test_single_instance_lock(tmp_path):
    first=InstanceLock(tmp_path/'instance.lock')
    try:
        with pytest.raises(ValueError):InstanceLock(tmp_path/'instance.lock')
    finally:first.close()
    second=InstanceLock(tmp_path/'instance.lock');second.close()

def test_desktop_smoke(tmp_path):
    result=tmp_path/'result.json';smoke_test(result)
    assert json.loads(result.read_text())['ok']
