# astrbot_plugin_missAV

MissAV视频信息查询插件

## 功能

- `/missav <视频ID>` - 获取视频信息和封面图
- `/missavsearch <关键词>` - 搜索视频

## 配置

在 AstrBot 管理面板中可设置：

- `display_fields` - 显示属性选择。可选：番号、标题、中文标题、发行日期、详情、女优、男优、类型、发行商、系列、磁链、封面。
- `enable_forward` - 是否开启合并转发形式发送影片信息（仅支持 aiocqhttp 平台）。
- `missav_blur_level` - 封面图模糊程度（0为不模糊，默认5）。
- `missav_proxy` - 代理地址，例如 `http://127.0.0.1:7890`。

## 安装

通过AstrBot插件管理安装：
```
https://github.com/vmoranv/astrbot_plugin_missAV
```

## 依赖

- aiohttp
- Pillow
- beautifulsoup4
- lxml
