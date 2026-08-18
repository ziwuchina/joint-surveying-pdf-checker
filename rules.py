"""规则配置加载模块。

将原先硬编码在代码里的项目相关规则（建筑名别名、功能分类关键词、楼层标签字段）
抽取到外部 rules.json，实现"新项目不改代码、只改配置"的通用化。
找不到配置文件时回退到内置默认规则，向后兼容。
"""
import json
import os

_DEFAULT_RULES = {
    "建筑名称别名": {
        # 格式: "标准名(以checker内建解析名或任意一个名称为基准)": ["别名1", "别名2", ...]
        # 匹配时：任一别名 normalize 后 与 目标名 normalize 后 相等即视为同一建筑。
    },
    "子项功能分类": {
        "roof": ["屋面", "屋顶", "梯屋", "机房", "楼梯间"],
        "facility": ["配套", "消防", "水泵", "配电", "发电机", "开关站", "水池",
                     "民生服务港", "公交首末站", "公共服务", "架空活动"],
        "basement": ["地下"],
        "main": ["主要功能", "厂房", "车间", "商业", "住宅", "办公", "宿舍",
                 "教育", "停车", "服务型公寓", "公寓"],
    },
    "楼层标签字段": {
        "unshared": ["不分摊"],
        "public": ["公建", "公共"],
        "workshop": ["车间", "套内"],
    },
}

_RULES = None


def _load_rules() -> dict:
    global _RULES
    if _RULES is not None:
        return _RULES
    rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")
    loaded = {}
    if os.path.exists(rules_path):
        try:
            with open(rules_path, encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError):
            loaded = {}
    # 深度合并：配置里没有的键用默认值
    merged = json.loads(json.dumps(_DEFAULT_RULES))
    for section in ("建筑名称别名", "子项功能分类", "楼层标签字段", "分项名称别名"):
        if section in loaded and isinstance(loaded[section], dict):
            for k, v in loaded[section].items():
                if isinstance(v, list):
                    merged.setdefault(section, {})[k] = list(v)
                else:
                    merged.setdefault(section, {})[k] = v
    _RULES = merged
    return _RULES


def get_subitem_category(label: str) -> str:
    """按配置关键词将分项标签分类：roof / facility / basement / main / other"""
    rules = _load_rules()
    label_clean = label.replace("\n", "").replace(" ", "")
    cats = rules.get("子项功能分类", {})
    # 保持判定顺序：roof → facility → basement → main
    for cat in ("roof", "facility", "basement", "main"):
        for kw in cats.get(cat, []):
            if kw and kw in label_clean:
                return cat
    return "other"


def get_floor_label_field(label: str) -> str:
    """按配置关键词判定楼层明细标签归属字段：unshared / public / workshop / None"""
    rules = _load_rules()
    label_clean = label.replace("\n", "").replace(" ", "")
    fields = rules.get("楼层标签字段", {})
    if any(kw and kw in label_clean for kw in fields.get("unshared", [])):
        return "unshared"
    if any(kw and kw in label_clean for kw in fields.get("public", [])):
        return "public"
    if any(kw and kw in label_clean for kw in fields.get("workshop", [])):
        return "workshop"
    return None


def get_building_aliases() -> dict:
    """返回建筑名称别名表（标准名 → 别名列表）"""
    return _load_rules().get("建筑名称别名", {})


def get_subitem_aliases() -> dict:
    """返回分项名称别名表（标准名 → 别名列表），用于 EDB/PDF 分项名跨项目统一"""
    return _load_rules().get("分项名称别名", {})
