# astrbot_plugin_missAV

MissAV视频信息查询插件

## 功能

- `/missav <视频ID>` - 获取视频信息和封面图
- `/missavsearch <关键词>` - 搜索视频

## 配置

在AstrBot配置中可设置：
- `missav_proxy` - 代理地址（可选）
- `missav_blur_level` - 封面图模糊程度（0为不模糊，默认20）

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
