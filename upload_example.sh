prefix=`cd upload && ls last-*`
prefix=${prefix%-20*}
if [ -n "$prefix" ]; then 
    rclone delete tencent-cos:/iph-1258787308 --include "$prefix*" || 0
fi
rclone copy upload/ tencent-cos:/iph-1258787308 --progress