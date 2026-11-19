# 从 Blender 工程构建格温皮肤

以下命令在 Windows PowerShell 的仓库根目录执行。只安装皮肤的玩家可以直接[下载成品](https://github.com/kazusa000/blg-gwen-skin/releases/latest/download/Gwen1-BLG.fantome)。

## 准备工作

1. 下载本标签配套的完整 Blender 文件，放到 `skin/Gwen1/Gwen1-BLG.blend`。贴图已经打包进母版。它也能单独在 Blender 打开。[v1.5.3 母版](https://github.com/kazusa000/blg-gwen-skin/releases/download/v1.5.3/Gwen1-BLG.blend)
2. 准备 Blender 5.1、Python 3.12、Node.js 24、Windows 的 .NET Framework 4.x 和可用的 DX11 设备。把 Python、Node 和 Blender 加入 PATH，安装 Python 依赖。

   ```powershell
   python -m pip install numpy==2.3.5 Pillow==13.0.0
   ```

3. 把 `ritobin-tools.exe` 放在 `tool/ritobin-0.2.3/`。将 CommunityDragon 的 `hashes.binfields.txt` 和 `hashes.bintypes.txt` 放到 `tool/hashes/`，此目录只放这两张表。构建脚本使用数值对象键和可读的字段名。[ritobin-tools v0.2.3](https://github.com/LeagueToolkit/ritobin-tools/releases/tag/v0.2.3) · [CommunityDragon 哈希表](https://github.com/CommunityDragon/Data/tree/master/hashes/lol)
4. 从 cslol-manager 的 Windows 发行版取得 `cslol-tools` 中的工具，保留同目录依赖，将 `GWEN_MOD_TOOLS` 指向 `mod-tools.exe`。将 `GWEN_GAME` 指向本机含有 `DATA/FINAL` 的游戏目录。本版构建使用的客户端数据版本是 **16.23.8399929**。后续补丁可能更换动画、粒子或着色器资源。[cslol-manager Releases](https://github.com/LeagueToolkit/cslol-manager/releases)

   ```powershell
   $env:GWEN_GAME = 'C:/Riot Games/League of Legends/Game'
   $env:GWEN_MOD_TOOLS = 'C:/Tools/cslol-manager/cslol-tools/mod-tools.exe'
   ```

如工具装在其他位置，可设置 `GWEN_BLENDER`、`GWEN_RITOBIN` 和 `GWEN_HASHES`，分别指向 Blender 可执行文件、ritobin 可执行文件和上述两张表所在的目录。

## 构建和校验

```powershell
python build.py
```

成品写到 `skin/Gwen1/Gwen1-BLG-1.5.3.fantome`。导出器从母版读取模型、实际变形权重和发丝，重绘角色和武器图集，再编译粒子、回城和玩偶。打包器会运行两轮导入校验，逐个回读 103 项资源，核对 SHA-256，并检查角色、剪刀和玩偶使用的 36 项 DX11 顶点及像素着色器请求。资源检查结果保存在 `source/Gwen1/recall/build/full-source/report.json`。

## 只重建改动的部分

| 编辑内容 | 运行方法 |
| --- | --- |
| 从本机游戏提取基础资源、载入本版的六视角投射图 | `python build.py --stage prepare` |
| 修改脸部、毛领或打光后，重新从 Blender 拍摄投射图 | 在 prepare 之后运行 `python build.py --stage capture`，随后依次运行 export、paint、package |
| 从 Blender 重新导出人物、发丝和武器 | `python build.py --stage export` |
| 重新烘焙贴图和材质 | `python build.py --stage paint` |
| 修改 E 或 R 粒子后用现有模型重新打包 | `python build.py --stage package` |

上述分步操作共用同一套构建目录。普通全量构建使用仓库中的投射图。自行重拍后，要保留新拍的输入，可将生成的 `full-source/face`、`full-source/pile` 文件更新到 `source/Gwen1/inputs/projections/`。

回城的队旗、奖杯、动作和闪烁分别由 `props.py`、`recall_cup.py`、`motion.py` 和 `recall_polish.py` 描述。独立的 2233 玩偶造型与图集在 `source/Gwen1/plush_2233/`。本版沿用的 Q、W 发射器、动画图及原生附件保存在 `recall/gameplay-resources.zip` 中，内部按游戏资源路径组织。修改这些基础资源时需要更新同名 ZIP 条目。最终打包器会在这份输入上应用本版的技能和回城调整。
