TODO:

* 组合文件并调用浏览器下载接口
* 替换下载库为 axios，支持请求取消和进度回调
* 下载失败重试
* 下载超时处理
* 下载进度显示
    * 美观的图形化显示
        * 需要实现CSS水平浮动布局
        * 需要实现CSS进度条显示
* 支持 query 传递 shrink 包 url
    * 目前已验证浏览器 indexDB 是按 host 划分的，无视 query
    * 对象存储需要设置为支持跨域