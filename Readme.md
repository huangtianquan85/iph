TODO:

-   python 改回 seek，降低运行时内存占用
-   测试 apk，zip 是否会因为签名的不同，不同包内相同的文件会发生变化
-   下载失败重试
-   Chrome 卡 pending 问题排查
-   下载超时处理
-   统计缓存大小
-   清理缓存
-   记录原始 zip 的 MD5
    -   记录到服务器数据库 / 记录到 shrink zip ？
-   ipa 如何实现增量
    -   ipa 必须通过 plist 从 https 下载，很难本地实现增量
    -   只能公司内部测试使用内网加速，外部测试走 TF 通道
