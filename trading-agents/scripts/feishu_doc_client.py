#!/usr/bin/env python3
"""
飞书文档 API 客户端
==================
封装飞书 OpenAPI 的文档操作：创建文档、写入 blocks、更新 blocks、获取文档信息。

自动从 ~/.openclaw/openclaw.json 读取飞书 trading 账号的 app_id/app_secret。
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_CREATE_DOC_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
FEISHU_BLOCKS_URL = "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}/children"
FEISHU_UPDATE_BLOCK_URL = "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}"
FEISHU_LIST_BLOCKS_URL = "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}/children"
FEISHU_DOC_INFO_URL = "https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"


class FeishuDocClient:
    """飞书文档 API 客户端。"""

    def __init__(self, account_id: str = "trading"):
        self.account_id = account_id
        self._token: Optional[str] = None
        self._token_expire: float = 0
        self._app_id: Optional[str] = None
        self._app_secret: Optional[str] = None
        self._load_credentials()

    def _load_credentials(self):
        """从 OpenClaw 配置中加载飞书凭证。"""
        if not OPENCLAW_CONFIG.exists():
            raise FileNotFoundError(f"OpenClaw config not found: {OPENCLAW_CONFIG}")

        with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        accounts = cfg.get("channels", {}).get("feishu", {}).get("accounts", {})
        account = accounts.get(self.account_id)
        if not account:
            raise RuntimeError(f"Feishu account '{self.account_id}' not found in openclaw.json")

        self._app_id = account.get("appId")
        self._app_secret = account.get("appSecret")
        if not self._app_id or not self._app_secret:
            raise RuntimeError(f"Missing appId/appSecret for Feishu account: {self.account_id}")

    def _get_token(self) -> str:
        """获取 tenant_access_token，带缓存。"""
        if self._token and time.time() < self._token_expire - 300:
            return self._token

        resp = requests.post(
            FEISHU_TOKEN_URL,
            json={"app_id": self._app_id, "app_secret": self._app_secret},
            timeout=15,
        )

        if resp.status_code >= 400:
            print("\n[FEISHU DEBUG] get token HTTP failed")
            print("[FEISHU DEBUG] status:", resp.status_code)
            print("[FEISHU DEBUG] response:", resp.text[:3000])

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print("\n[FEISHU DEBUG] get token API failed")
            print("[FEISHU DEBUG] response:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            raise RuntimeError(f"Get token failed: {data}")

        self._token = data["tenant_access_token"]
        self._token_expire = time.time() + data.get("expire", 7200)
        return self._token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def create_document(self, title: str, folder_token: Optional[str] = None) -> Dict[str, Any]:
        """创建空白文档。

        Returns:
            {"document_id": "xxx", "url": "https://..."}
        """
        payload: Dict[str, Any] = {"title": title}
        if folder_token:
            payload["folder_token"] = folder_token

        resp = requests.post(
            FEISHU_CREATE_DOC_URL,
            headers=self._headers(),
            json=payload,
            timeout=15,
        )

        if resp.status_code >= 400:
            print("\n[FEISHU DEBUG] create_document HTTP failed")
            print("[FEISHU DEBUG] status:", resp.status_code)
            print("[FEISHU DEBUG] response:", resp.text[:3000])

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print("\n[FEISHU DEBUG] create_document API failed")
            print("[FEISHU DEBUG] response:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            raise RuntimeError(f"Create document failed: {data}")

        doc_info = data["data"]["document"]
        return {
            "document_id": doc_info["document_id"],
            "url": f"https://bigdatacenter.feishu.cn/docx/{doc_info['document_id']}",
            "title": doc_info.get("title", title),
        }

    def append_blocks(
        self,
        document_id: str,
        blocks: List[Dict],
        parent_block_id: Optional[str] = None,
        index: int = -1,
    ) -> Dict[str, Any]:
        """在文档中插入 blocks。

        Args:
            document_id: 文档 ID
            blocks: block 列表，每个 block 是 {"block_type": 2, "text": {...}} 等格式
            parent_block_id: 父 block ID，默认文档根节点
            index: 插入位置，-1 表示末尾，0 表示开头
        """
        block_id = parent_block_id or document_id
        url = FEISHU_BLOCKS_URL.format(doc_id=document_id, block_id=block_id)

        payload = {"children": blocks}
        if index != -1:
            payload["index"] = index

        resp = requests.post(
            url,
            headers=self._headers(),
            json=payload,
            timeout=30,
        )

        if resp.status_code >= 400:
            print("\n[FEISHU DEBUG] append_blocks HTTP failed")
            print("[FEISHU DEBUG] status:", resp.status_code)
            print("[FEISHU DEBUG] url:", url)
            print("[FEISHU DEBUG] document_id:", document_id)
            print("[FEISHU DEBUG] parent_block_id:", block_id)
            print("[FEISHU DEBUG] index:", index)
            print("[FEISHU DEBUG] block_count:", len(blocks))
            print("[FEISHU DEBUG] response text:")
            print(resp.text[:5000])

            print("\n[FEISHU DEBUG] first blocks preview:")
            for i, block in enumerate(blocks[:5]):
                try:
                    print(f"[FEISHU DEBUG] block[{i}]:")
                    print(json.dumps(block, ensure_ascii=False, indent=2)[:2500])
                except Exception as e:
                    print(f"[FEISHU DEBUG] block[{i}] dump failed: {e}")
                    print(str(block)[:2500])

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print("\n[FEISHU DEBUG] append_blocks API returned non-zero code")
            print("[FEISHU DEBUG] data:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
            print("[FEISHU DEBUG] block_count:", len(blocks))

            print("\n[FEISHU DEBUG] first blocks preview:")
            for i, block in enumerate(blocks[:5]):
                try:
                    print(f"[FEISHU DEBUG] block[{i}]:")
                    print(json.dumps(block, ensure_ascii=False, indent=2)[:2500])
                except Exception as e:
                    print(f"[FEISHU DEBUG] block[{i}] dump failed: {e}")
                    print(str(block)[:2500])

            raise RuntimeError(f"Append blocks failed: {data}")

        return data["data"]

    def update_block(self, document_id: str, block_id: str, block_data: Dict) -> Dict[str, Any]:
        """更新指定 block 的内容。"""
        url = FEISHU_UPDATE_BLOCK_URL.format(doc_id=document_id, block_id=block_id)

        resp = requests.patch(
            url,
            headers=self._headers(),
            json=block_data,
            timeout=15,
        )

        if resp.status_code >= 400:
            print("\n[FEISHU DEBUG] update_block HTTP failed")
            print("[FEISHU DEBUG] status:", resp.status_code)
            print("[FEISHU DEBUG] url:", url)
            print("[FEISHU DEBUG] response:", resp.text[:3000])

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print("\n[FEISHU DEBUG] update_block API failed")
            print("[FEISHU DEBUG] data:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            raise RuntimeError(f"Update block failed: {data}")

        return data["data"]

    def list_blocks(
        self,
        document_id: str,
        parent_block_id: Optional[str] = None,
        page_size: int = 500,
    ) -> List[Dict]:
        """列出文档中的所有 blocks。"""
        block_id = parent_block_id or document_id
        url = FEISHU_LIST_BLOCKS_URL.format(doc_id=document_id, block_id=block_id)

        all_items = []
        page_token = ""

        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(url, headers=self._headers(), params=params, timeout=15)

            if resp.status_code >= 400:
                print("\n[FEISHU DEBUG] list_blocks HTTP failed")
                print("[FEISHU DEBUG] status:", resp.status_code)
                print("[FEISHU DEBUG] url:", url)
                print("[FEISHU DEBUG] response:", resp.text[:3000])

            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                print("\n[FEISHU DEBUG] list_blocks API failed")
                print("[FEISHU DEBUG] data:")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
                raise RuntimeError(f"List blocks failed: {data}")

            items = data["data"].get("items", [])
            all_items.extend(items)

            if not data["data"].get("has_more"):
                break

            page_token = data["data"].get("page_token", "")

        return all_items

    def delete_block(self, document_id: str, block_id: str) -> Dict[str, Any]:
        """删除指定 block。"""
        url = FEISHU_UPDATE_BLOCK_URL.format(doc_id=document_id, block_id=block_id)

        resp = requests.delete(url, headers=self._headers(), timeout=15)

        if resp.status_code >= 400:
            print("\n[FEISHU DEBUG] delete_block HTTP failed")
            print("[FEISHU DEBUG] status:", resp.status_code)
            print("[FEISHU DEBUG] url:", url)
            print("[FEISHU DEBUG] response:", resp.text[:3000])

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print("\n[FEISHU DEBUG] delete_block API failed")
            print("[FEISHU DEBUG] data:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            raise RuntimeError(f"Delete block failed: {data}")

        return data.get("data", {})

    def get_doc_info(self, document_id: str) -> Dict[str, Any]:
        """获取文档基本信息。"""
        url = FEISHU_DOC_INFO_URL.format(doc_id=document_id)
        resp = requests.get(url, headers=self._headers(), timeout=15)

        if resp.status_code >= 400:
            print("\n[FEISHU DEBUG] get_doc_info HTTP failed")
            print("[FEISHU DEBUG] status:", resp.status_code)
            print("[FEISHU DEBUG] url:", url)
            print("[FEISHU DEBUG] response:", resp.text[:3000])

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            print("\n[FEISHU DEBUG] get_doc_info API failed")
            print("[FEISHU DEBUG] data:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            raise RuntimeError(f"Get doc info failed: {data}")

        return data["data"]["document"]


# =============================================================================
# Block 构建工具函数
# =============================================================================

def text_block(content: str, bold: bool = False, italic: bool = False, color: int = 0) -> Dict:
    """创建文本块。"""
    style = {}
    if bold:
        style["bold"] = True
    if italic:
        style["italic"] = True
    if color:
        style["text_color"] = color

    element = {"text_run": {"content": content}}
    if style:
        element["text_run"]["text_element_style"] = style

    return {
        "block_type": 2,
        "text": {"elements": [element]},
    }


def heading1_block(content: str) -> Dict:
    return {
        "block_type": 3,
        "heading1": {"elements": [{"text_run": {"content": content}}]},
    }


def heading2_block(content: str) -> Dict:
    return {
        "block_type": 4,
        "heading2": {"elements": [{"text_run": {"content": content}}]},
    }


def heading3_block(content: str) -> Dict:
    return {
        "block_type": 5,
        "heading3": {"elements": [{"text_run": {"content": content}}]},
    }


def divider_block() -> Dict:
    return {
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": "─────────────────────────────────"}}]},
    }


def bullet_block(content: str) -> Dict:
    return {
        "block_type": 2,
        "text": {"elements": [{"text_run": {"content": f"• {content}"}}]},
    }


def ordered_block(content: str) -> Dict:
    return {
        "block_type": 20,
        "ordered_list": {"elements": [{"text_run": {"content": content}}]},
    }


def quote_block(content: str) -> Dict:
    return {
        "block_type": 2,
        "text": {
            "elements": [
                {
                    "text_run": {
                        "content": f"「 {content} 」",
                        "text_element_style": {"italic": True},
                    }
                }
            ],
            "style": {"align": 1},
        },
    }


FEISHU_COLORS = {
    "default": 0,
    "gray": 1,
    "brown": 2,
    "orange": 3,
    "yellow": 4,
    "green": 5,
    "blue": 6,
    "purple": 7,
    "pink": 8,
    "red": 9,
    "light_gray": 10,
    "dark_gray": 11,
    "dark_brown": 12,
    "dark_orange": 13,
    "dark_yellow": 14,
    "dark_green": 15,
    "dark_blue": 16,
    "dark_purple": 17,
    "dark_pink": 18,
    "dark_red": 19,
}