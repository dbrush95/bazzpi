"""Bazzpi persistent state and validated launch commands (standard library only)."""
import copy
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import time

DEFAULTS = dict(theme='light', wallpaper='Cloud', wallpaper_file='', host='',
                desktop_mode='Moonlight', desktop_app='Desktop', rdp_host='',
                share='', resolution='1920x1080', fps=60, bitrate=20,
                codec='H.264', stream_tty=True, display_mode='1920x1080', underscan=0)
SYSTEMS = [
 ('NES','nes','lr-fceumm'), ('SNES','snes','lr-snes9x2010'),
 ('Game Boy','gb','lr-gambatte'), ('Game Boy Color','gbc','lr-gambatte'),
 ('Game Boy Advance','gba','lr-mgba'), ('Master System','mastersystem','lr-genesis-plus-gx'),
 ('Genesis','megadrive','lr-genesis-plus-gx'), ('Game Gear','gamegear','lr-genesis-plus-gx'),
 ('Sega CD','segacd','lr-genesis-plus-gx'), ('32X','sega32x','lr-picodrive'),
 ('TurboGrafx-16','pcengine','lr-beetle-pce-fast'), ('PC Engine CD','pcengine','lr-beetle-pce-fast'),
 ('Neo Geo','neogeo','lr-fbneo'), ('Neo Geo Pocket','ngp','lr-beetle-ngp'),
 ('WonderSwan','wonderswan','lr-beetle-wswan'), ('Atari 2600','atari2600','lr-stella2014'),
 ('Atari 7800','atari7800','lr-prosystem'), ('Atari Lynx','atarilynx','lr-handy'),
 ('Intellivision','intellivision','lr-freeintv'), ('ColecoVision','coleco','lr-bluemsx'),
 ('FBNeo arcade','fba','lr-fbneo'), ('MAME 2003','mame-libretro','lr-mame2003'),
 ('Commodore 64','c64','lr-vice'), ('Amiga','amiga','lr-puae'),
 ('DOS','pc','dosbox'), ('ScummVM','scummvm','scummvm'),
 ('PlayStation','psx','lr-pcsx-rearmed'), ('Nintendo 64','n64','lr-mupen64plus-next'),
 ('Dreamcast','dreamcast','lr-flycast'), ('PSP','psp','ppsspp'),
 ('Nintendo DS','nds','lr-desmume')]


def host(value):
    value = value.strip()
    if not value or len(value) > 253 or value.startswith('-'):
        raise ValueError('Enter the PC IP address or hostname, without a URL or port.')
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', value):
            raise ValueError('Use an IP address or hostname without spaces, a URL, or a port.')
        if any(not x or len(x) > 63 or x.startswith('-') or x.endswith('-') for x in value.split('.')):
            raise ValueError('Invalid hostname.')
        return value


def sunshine_url(value):
    value = host(value)
    return 'https://' + ('[' + value + ']' if ':' in value else value) + ':47990'


def stream_args(settings, app):
    pc = host(settings['host'])
    if not app.strip() or len(app) > 200 or '\n' in app or app.startswith('-'):
        raise ValueError('Enter a Sunshine app name, for example Steam or Desktop.')
    if settings['resolution'] not in ('1280x720','1920x1080'):
        raise ValueError('Pi 4 presets are 720p or 1080p.')
    if int(settings['fps']) not in (30,60) or not 5 <= int(settings['bitrate']) <= 40:
        raise ValueError('Select 30/60 fps and 5–40 Mb/s.')
    if settings['codec'] not in ('H.264','HEVC'):
        raise ValueError('Unsupported codec.')
    return ['stream','--resolution',settings['resolution'],'--fps',str(settings['fps']),
            '--bitrate',str(int(settings['bitrate'])*1000),'--video-codec',settings['codec'],
            '--display-mode','fullscreen',pc,app.strip()]


def pin_record(code):
    if code and not re.fullmatch('[0-9]{4}', code):
        raise ValueError('The optional code must contain exactly four digits.')
    if not code:
        return None
    salt = secrets.token_hex(16)
    return dict(salt=salt, digest=hashlib.pbkdf2_hmac('sha256',code.encode(),bytes.fromhex(salt),240000).hex())


def verify_pin(record, code):
    if record is None:
        return True
    if not re.fullmatch('[0-9]{4}', code):
        return False
    test = hashlib.pbkdf2_hmac('sha256',code.encode(),bytes.fromhex(record['salt']),240000).hex()
    return hmac.compare_digest(test, record['digest'])


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get('BAZZPI_STATE', str(Path.home()/'.config/bazzpi')))
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path = self.directory/'state.json'
        self.data = dict(settings=copy.deepcopy(DEFAULTS), profile=None, failures=0, retry_at=0)
        if self.path.exists():
            # Fail closed; never silently discard a corrupt profile and bypass its PIN.
            loaded = json.loads(self.path.read_text())
            if not isinstance(loaded,dict) or 'profile' not in loaded:
                raise ValueError('Invalid profile file. Restore state.json from backup.')
            self.data.update(loaded)
            self.data['settings'] = {**DEFAULTS, **loaded.get('settings',{})}

    @property
    def settings(self):
        return self.data['settings']

    def save(self):
        temp = self.directory/('state.'+secrets.token_hex(6)+'.tmp')
        fd = os.open(temp, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            json.dump(self.data,f,indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,self.path)

    def create_profile(self,name,code):
        if self.data['profile'] is not None:
            raise ValueError('A profile already exists.')
        name=name.strip()
        if not 1 <= len(name) <= 40:
            raise ValueError('Enter a name between 1 and 40 characters.')
        self.data['profile']=dict(name=name,pin=pin_record(code))
        self.save()

    def unlock(self,code,now=None):
        now=time.time() if now is None else now
        if now < self.data['retry_at']:
            return False
        if verify_pin(self.data['profile']['pin'],code):
            self.data.update(failures=0,retry_at=0)
            self.save()
            return True
        failures=self.data['failures']+1
        self.data.update(failures=failures,retry_at=now+min(300,30*2**min(4,failures-5)) if failures>=5 else 0)
        self.save()
        return False
