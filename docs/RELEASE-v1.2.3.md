# Research Hub v1.2.3

修正版。功能與 v1.2.2 相同（功能說明見 `docs/RELEASE-v1.2.1.md`），這一版處理 Windows 上「雙擊 start 打不開」的問題。

## 修正
- **Windows 啟動檔 `start.cmd` 重寫**
  - 找不到 Python 時，顯示下載網址與安裝提醒，視窗會停住，不再一閃就關。
  - Python 版本低於 3.10 時，顯示目前版本並說明需要更新。
  - 啟動失敗時視窗會停住，看得到錯誤訊息。
- **連接埠被占用時給明確提示**：Research Hub 可能已在執行，可直接開瀏覽器，或用 `start.cmd --port 8771` 換連接埠。
- 移除誤放進套件的 `srv.log` 紀錄檔。
- 程式內的版本號與 release 名稱對齊為 1.2.3。

## Windows 第一次使用
1. 到 https://www.python.org/downloads/ 安裝 Python 3.10 以上，安裝時勾選「Add python.exe to PATH」。
2. 解壓縮後雙擊 `start`。黑色視窗出現後，瀏覽器會自動開啟 `http://127.0.0.1:8770/`。
3. 使用期間黑色視窗要保持開著，關掉就停止。

## 尚未在實機驗證
新的 `start.cmd` 是在 Linux 環境撰寫，沒有在 Windows 上實際執行過；若仍無法啟動，請回報視窗顯示的訊息。

## 升級
直接用新版開啟原本的工作區即可，資料不會變動。
