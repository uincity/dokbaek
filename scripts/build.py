"""Produce a release solely from the explicit allowlist; no third-party packages."""
from pathlib import Path
import json, shutil, struct, uuid
from validate import ROOT, approved_files, validate_data, validate_dist, require

def strip_metadata(data,suffix):
    if suffix=='.png':
        require(data.startswith(b'\x89PNG\r\n\x1a\n'),'Invalid PNG')
        out=data[:8];offset=8
        while offset<len(data):
            n=struct.unpack_from('>I',data,offset)[0];chunk=data[offset:offset+n+12]
            require(len(chunk)==n+12,'Truncated PNG')
            if chunk[4:8] not in {b'tEXt',b'zTXt',b'iTXt',b'eXIf'}:out+=chunk
            offset+=n+12
        return out
    if suffix in {'.jpg','.jpeg'}:
        require(data[:2]==b'\xff\xd8','Invalid JPEG')
        out=data[:2];offset=2
        while offset<len(data):
            require(data[offset]==255,'Invalid JPEG marker')
            start=offset
            while data[offset]==255:offset+=1
            marker=data[offset];offset+=1
            if marker==0xda:return out+data[start:]
            if marker==0xd9:return out+data[start:offset]
            length=int.from_bytes(data[offset:offset+2],'big')
            chunk=data[start:offset+length];require(len(chunk)==offset+length-start,'Truncated JPEG')
            if marker not in {0xe1,0xed,0xfe}:out+=chunk
            offset+=length
        return out
    return data

def build():
    info=validate_data()
    target=(ROOT/'dist').resolve()
    require(target.parent==ROOT.resolve() and target.name=='dist','Build target must be workspace/dist')
    require(not target.is_symlink(),'Refusing a linked dist directory')
    # Validate in an isolated staging directory before replacing the generated output.
    staging=ROOT/('.release-'+uuid.uuid4().hex)
    staging.mkdir()
    try:
        for rel in approved_files()+info['files']:
            src=ROOT/rel;dst=staging/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            if rel.startswith('data/concerts-'):
                public=[c for c in json.loads(src.read_text(encoding='utf-8')) if c['visibility'] in {'public','public-summary'}]
                dst.write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            elif src.suffix.lower() in {'.png','.jpg','.jpeg'}:dst.write_bytes(strip_metadata(src.read_bytes(),src.suffix.lower()))
            else:shutil.copyfile(src,dst)
        (staging/'.nojekyll').touch()
        validate_dist(staging)
        if target.exists():shutil.rmtree(target)
        shutil.copytree(staging,target)
    finally:
        # The resolved staging target must remain directly inside this workspace.
        require(staging.resolve().parent==ROOT.resolve() and staging.name.startswith('.release-'),'Unsafe staging cleanup')
        if staging.exists():shutil.rmtree(staging)
    validate_dist(target)
    print('PASS: reviewed public files built and validated in dist/. Originals were preserved.')

if __name__=='__main__':build()
