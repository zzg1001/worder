# -*- coding: utf-8 -*-
"""
wechat_crypto.py - 微信消息加解密（原文件）
"""

import base64
import hashlib
import logging
import xml.etree.ElementTree as ET
from Crypto.Cipher import AES

logger = logging.getLogger(__name__)


class WXBizMsgCrypt:
    def __init__(self, token, aes_key, corp_id):
        self.token = token
        self.corp_id = corp_id
        try:
            self.key = base64.b64decode(aes_key + "=")
        except Exception as e:
            logger.error(f"AESKey解码失败: {e}")
            raise

    def verify_url(self, sig, ts, nonce, echo):
        if not self._check_sig(sig, ts, nonce, echo):
            raise ValueError("signature验证失败")
        return self._decrypt(echo)

    def decrypt_msg(self, sig, ts, nonce, post_data):
        try:
            root = ET.fromstring(post_data)
            encrypt = root.find("Encrypt")
            if encrypt is None:
                raise ValueError("XML中缺少Encrypt节点")
            encrypt = encrypt.text

            if not self._check_sig(sig, ts, nonce, encrypt):
                raise ValueError("signature验证失败")
            return self._decrypt(encrypt)
        except ET.ParseError as e:
            logger.error(f"XML解析失败: {e}")
            raise ValueError(f"XML解析失败: {e}")

    def _check_sig(self, sig, ts, nonce, encrypt):
        sort_str = "".join(sorted([self.token, str(ts), str(nonce), encrypt]))
        hash_str = hashlib.sha1(sort_str.encode()).hexdigest()
        return sig == hash_str

    def _decrypt(self, text):
        try:
            cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            decrypt_data = base64.b64decode(text)
            plain = cipher.decrypt(decrypt_data)

            pad_len = plain[-1]
            if isinstance(pad_len, int):
                content = plain[:-pad_len]
            else:
                content = plain[:-ord(pad_len)]

            if len(content) < 20:
                raise ValueError("解密后数据太短")

            msg_len = int.from_bytes(content[16:20], byteorder='big')
            msg_content = content[20:20 + msg_len].decode('utf-8')
            from_corpid = content[20 + msg_len:].decode('utf-8')

            if from_corpid != self.corp_id:
                raise ValueError(f"CorpID不匹配: {from_corpid} != {self.corp_id}")

            return msg_content
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise ValueError(f"解密失败: {e}")