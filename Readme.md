## TODO:

-   Android 版本
    -   转换工程到 Kotlin 项目
    -   使用 Kotlin 实现 package_loader.js 的功能，js 端只保留 HTML 用来实时显示 Android 端传过来的进度数据
        -   使用写入大文件的方式，使用 KV 数据库记录 Blob 的位置，每次新下载的文件，在都下载完成后追加到大文件末尾
        -   或者直接使用高性能的类似 IndexedDB 的键值数据库，MMKV，RocksDB，Realm 等
            -   https://github.com/Tencent/MMKV/blob/master/README_CN.md
            -   小文件使用 MMKV 存储，大文件直接使用文件存储
    -   实现卸载旧 App
-   实现 Rust 版本的 unpacker 和 downloader
-   实现一个缓冲服务器（可以解决 iOS 安装的问题和 Android 浏览器不兼容的问题，算是一个补充方案）
-   ipa 如何实现增量
    -   ipa 可以通过隔空投送安装，那么如果下载到本地也可以实现安装
    -   ipa 必须通过 plist 从 https 下载，很难本地实现增量
    -   只能公司内部测试使用内网加速，外部测试走 TF 通道
    -   如果实在无法实现手机端增量，只能用公网写文件流的方式了
-   下载失败，超时，卡住，Chrome 卡 pending 等异常处理
-   校验分块 MD5，成功才进行缓存，失败重新下载

## Not TODO:

-   统计缓存大小
-   清理缓存
-   MEGA 的实现了一个生成下载的方法，有空可以测试一下手机上的兼容性
    -   https://mega.nz/file/7B5UVY6b#Hae2ceTBPIrTowQN0sV9fQ5lGOKzGxas2ug02RZAdGU
-   ~~解决浏览器 Blob 大小限制~~，浏览器兼容性太难解决了
    -   StreamSaver 方案依然无法适配所有浏览器
    -   StreamSaver 的推荐方案 Native File System Access 还处于提案阶段呢

## 参考

-   [前端自个突破浏览器 Blob 和 RAM 大小限制保存文件的骚玩法！](https://juejin.cn/post/6985883442122604574)
-   [前端 JS 下载大文件解决方案](https://www.cnblogs.com/mrwh/p/13227709.html)
-   [StreamSaver.js](https://github.com/jimmywarting/StreamSaver.js)
