"""Exercise panel restore plans against a disposable in-memory remote filesystem."""
import copy
import hashlib
import io
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import deploy_panel as deploy


class MemorySFTP:
    def __init__(self,files):self.files=files;self.modes={p:0o644 for p in files}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def lstat(self,path):
        if path not in self.files:raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=stat.S_IFREG|self.modes.get(path,0o644))
    def open(self,path,mode):
        if mode=='rb':return io.BytesIO(self.files[path])
        parent=self
        class Writer(io.BytesIO):
            def close(self):
                parent.files[path]=self.getvalue();super().close()
        return Writer()
    def chmod(self,path,mode):self.modes[path]=mode
    def posix_rename(self,source,target):self.files[target]=self.files.pop(source);self.modes[target]=self.modes.pop(source)
    def remove(self,path):del self.files[path]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        folder=self.root/'recordings/test';folder.mkdir(parents=True)
        self.original={};remote={};items=[]
        for i,(source,target) in enumerate(deploy.FILES.items()):
            path=deploy.REMOTE+'/'+target;before=f'original {i}'.encode() if i%2==0 else None
            after=f'updated {i}'.encode();remote[path]=after
            backup=folder/f'{i}.bak'
            if before is not None:backup.write_bytes(before);self.original[path]=before
            items.append({'path':path,'source':source,'sha256':deploy.digest(after),
                'before_sha256':deploy.digest(before) if before else None,
                'before_mode':0o644 if before else None,'backup':str(backup.relative_to(self.root)) if before else None,'staging':path+'.panel-upload'})
        self.state={'unit_sha256':'unit-hash','UnitFileState':'enabled','ActiveState':'active','MainPID':'42'}
        self.plan={'id':'test','status':'applied','service_before':self.state,'files':items}
        self.manifest={'panel_updates':[self.plan]}
        self.sftp=MemorySFTP(remote)
        self.client=SimpleNamespace(open_sftp=lambda:self.sftp,close=lambda:None)
        self.patches=[patch.object(deploy,'ROOT',self.root),patch.object(deploy,'connect',return_value=self.client),
            patch.object(deploy,'load_manifest',return_value=self.manifest),patch.object(deploy,'save_manifest'),
            patch.object(deploy,'device_state',return_value=self.state),patch.object(deploy,'database_state',return_value={'counts':{'records':123},'raw_sha256':'unchanged'}),
            patch.object(deploy,'health',return_value={'status':'ok'}),patch.object(deploy,'run',return_value='')]
        self.mocks=[p.start() for p in self.patches]

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_dry_run_does_not_modify_files_or_service(self):
        before=copy.deepcopy(self.sftp.files);deploy.rollback_panel(False)
        self.assertEqual(self.sftp.files,before);self.mocks[-1].assert_not_called()
        self.assertEqual(self.plan['status'],'applied')

    def test_apply_restores_exact_original_files(self):
        deploy.rollback_panel(True)
        self.assertEqual(self.sftp.files,self.original)
        self.assertEqual(self.plan['status'],'rolled_back')
        self.assertEqual(self.mocks[-1].call_count,2)

    def test_foreign_edit_stops_before_service_change(self):
        self.sftp.files[self.plan['files'][0]['path']]=b'user changed it'
        with self.assertRaisesRegex(RuntimeError,'outside this deployment'):deploy.rollback_panel(True)
        self.mocks[-1].assert_not_called()

    def test_bad_backup_and_unexpected_path_are_rejected(self):
        item=self.plan['files'][0];(self.root/item['backup']).write_bytes(b'bad')
        with self.assertRaisesRegex(RuntimeError,'Backup checksum'):deploy.rollback_panel(True)
        self.mocks[-1].assert_not_called()
        item['path']='/unexpected'
        with self.assertRaisesRegex(RuntimeError,'unexpected files'):deploy.rollback_panel(True)

    def test_partial_deployment_restores_and_removes_owned_staging(self):
        item=self.plan['files'][0];self.sftp.files[item['path']]=self.original[item['path']]
        item=self.plan['files'][1];self.sftp.files[item['staging']]=self.sftp.files.pop(item['path'])
        deploy.rollback_panel(True)
        self.assertEqual(self.sftp.files,self.original)


if __name__=='__main__':unittest.main()
