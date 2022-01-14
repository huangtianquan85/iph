prefix=`cd upload && ls last-*`
prefix=${prefix%-20*}
rclone delete tencent-cos:/iph-1258787308 --include "$prefix*" || 0
rclone copy upload/ tencent-cos:/iph-1258787308 --progress