# usage: <upload.sh path> <remote_name:bucket_name>

prefix=${prefix%-20*}
if [ -n "$prefix" ]; then 
    <rclone_path> delete $1 --include "$prefix*" || 0
fi
<rclone_path> copy upload/ $1 --progress