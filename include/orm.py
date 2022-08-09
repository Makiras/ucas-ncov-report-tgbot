import datetime
from typing import List
from peewee import *
from playhouse.migrate import *
from .config import *
from .function import *

database_proxy = DatabaseProxy()
_logger = logging.getLogger(__name__)

class BaseModel(Model):
    class Meta:
        database = database_proxy

class UCASUserStatus:
    normal  = 0
    stopped = 1
    removed = 2
    warning = 3

class TGUser(BaseModel):
    id = AutoField()
    userid = IntegerField(unique=True)
    username = CharField(null=True, index=True)
    create_time = DateTimeField(default=datetime.datetime.now, index=True)

    def get_ucasusers_by_seqids(self, seqids: List[int]):
        available_targets = self.get_ucasusers()
        assert max(seqids) <= len(available_targets), "Seqid out of range."

        return [available_targets[i-1] for i in seqids]

    def get_ucasusers(self, include_all=False):
        if include_all:
            return self.ucasusers
        else:
            return self.ucasusers.where(UCASUser.status != UCASUserStatus.removed)

class UCASUser(BaseModel):
    id = AutoField()
    owner = ForeignKeyField(model=TGUser, backref='ucasusers', lazy_load=False, index=True, on_delete="CASCADE", on_update="CASCADE")
    username = CharField(null=True)
    password = CharField(null=True)
    cookie_eaisess = CharField(null=True)
    cookie_uukey = CharField(null=True)
    latest_data = TextField(null=True)
    latest_response_data = TextField(null=True)
    latest_response_time = DateTimeField(null=True, index=True)

    status = IntegerField(index=True, default=UCASUserStatus.normal)
    create_time = DateTimeField(default=datetime.datetime.now, index=True)
    update_time = DateTimeField(default=datetime.datetime.now, index=True)

    def save(self, *args, **kwargs):
        self.update_time = datetime.datetime.now()
        return super(UCASUser, self).save(*args, **kwargs)

    def check_status(self):
        assert self.status != UCASUserStatus.stopped
        assert self.status != UCASUserStatus.removed

    def login(self):
        self.check_status()
        assert self.username != None
        _logger.info(f"[login] Trying user: {self.username}")
        session = requests.Session()
        session.proxies.update(CHECKIN_PROXY)
        session.headers.update({'User-Agent': REQUESTS_USERAGENT})

        login_resp = session.post(LOGIN_API, data={
            'username': self.username,
            'password': self.password,
        }, timeout=API_TIMEOUT)
        _logger.debug(login_resp.text)
        if login_resp.status_code != 200:
            raise RuntimeError('Login Server ERROR!')

        ret_data = login_resp.json()
        if ret_data['e'] == 0:
            self.cookie_eaisess = login_resp.cookies['eai-sess']
            self.cookie_uukey = login_resp.cookies['UUkey']
            self.save()
            _logger.info(f'[login] Succeed! user: {self.username}.')
            return session
        else:
            _logger.warning(f'[login] Failed! user: {self.username}, ret: {ret_data}')
            raise RuntimeWarning(f'Login failed! Server return: `{ret_data}`')
    
    def pause(self):
        self.status = UCASUserStatus.stopped
        self.save()

    def ncov_checkin(self, force=False):
        if not force:
            self.check_status()
        session = requests.Session()
        session.proxies.update(CHECKIN_PROXY)
        session.headers.update({'User-Agent': REQUESTS_USERAGENT})
        if self.cookie_eaisess != None:
            cookies={
                'eai-sess': self.cookie_eaisess,
                'UUKey': self.cookie_uukey
            }
            requests.utils.add_dict_to_cookiejar(session.cookies, cookies)

        report_json_resp = session.get(REPORT_DATA_API, allow_redirects=False, timeout=API_TIMEOUT)
        _logger.debug(f'[report page] status: {report_json_resp.status_code}')
        if report_json_resp.status_code == 302:
            if self.username != None:
                session = self.login()
            else:
                self.status = UCASUserStatus.warning
                self.save()
                raise RuntimeWarning(f'Cookies expired with no login info set. Please update your cookie. \neai-sess:`{self.cookie_eaisess}`')
            report_json_resp = session.get(REPORT_DATA_API, allow_redirects=False, timeout=API_TIMEOUT)
        if report_json_resp.status_code != 200:
            RuntimeError(f'Report Page returned {report_json_resp.status_code}.')

        report_json_txt = report_json_resp.text
        assert '操作成功' in report_json_txt, "报告页面返回信息不正确"

        # 从接口中提取 POST 的参数
        try:
            post_data = extract_post_data(report_json_txt)
        except Exception as e:
            _logger.warning(f'[report page] Failed to extract post data. {e}')
            raise RuntimeError(f'Failed to generate post data. {e}')
        self.latest_data = json.dumps(post_data)
        self.save()
        _logger.debug(f'[report api] Final data: {post_data}')
        print(post_data)

        # 最终 POST
        report_api_resp = session.post(REPORT_API, data=post_data,
            # headers={ 'X-Requested-With': 'XMLHttpRequest'},
            timeout=API_TIMEOUT
        )
        assert report_api_resp.status_code == 200, "提交 API 状态异常"
        self.latest_response_data = report_api_resp.text.strip()
        self.latest_response_time = datetime.datetime.now()
        self.save()

        if report_api_resp.json()['e'] == 0:
            return report_api_resp.text.strip()
        else:
            raise Exception(report_api_resp.text.strip())


def db_init():
    database_proxy.connect()
    database_proxy.create_tables([TGUser,UCASUser])

