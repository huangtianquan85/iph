## TODO:

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
-   ~~解决浏览器 Blob 大小限制~~，浏览器兼容性太难解决了
    -   StreamSaver 方案依然无法适配所有浏览器
    -   StreamSaver 的推荐方案 Native File System Access 还处于提案阶段呢

## 参考

-   [前端自个突破浏览器 Blob 和 RAM 大小限制保存文件的骚玩法！](https://juejin.cn/post/6985883442122604574)
-   [前端 JS 下载大文件解决方案](https://www.cnblogs.com/mrwh/p/13227709.html)
-   [StreamSaver.js](https://github.com/jimmywarting/StreamSaver.js)
