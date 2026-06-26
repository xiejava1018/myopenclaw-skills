"""七牛云上传 provider。SDK 在 upload() 内懒导入，模块 import 不强制装 qiniu。"""
from . import Uploader, UploadResult, join_url


class QiniuUploader(Uploader):
    """七牛对象存储上传器。"""
    backend_name = "qiniu"

    def upload(self, local_path: str, key: str) -> UploadResult:
        # 懒导入：未装 qiniu SDK 也不影响其它后端
        from qiniu import Auth, put_file

        cfg = self.config
        auth = Auth(cfg.qiniu_access_key, cfg.qiniu_secret_key)
        token = auth.upload_token(cfg.qiniu_bucket, key)
        ret, info = put_file(token, key, local_path)

        # put_file 成功标志：resp_info.ok() 或 status_code==200
        ok = getattr(info, "ok", lambda: False)()
        if not ok and getattr(info, "status_code", None) != 200:
            raise RuntimeError(f"七牛上传失败: {info}")

        url = join_url(cfg.qiniu_domain, key)
        return UploadResult(backend="qiniu", key=key, url=url, extra={"ret": ret})
