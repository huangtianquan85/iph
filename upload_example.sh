prefix=`cd upload && ls last-*`
prefix=${prefix%-20*}
rclone delete tencent-cos:/autopkg-bj-1258787308 --include "$prefix*"
rclone copy upload/ tencent-cos:/autopkg-bj-1258787308 --progress