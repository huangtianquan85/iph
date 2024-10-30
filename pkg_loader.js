const threshold = 4096;
const hash_len = 16;

function get_hash_str(buffer, offset) {
    const hash_view = new Uint8Array(buffer, offset, hash_len);
    return [...hash_view].map((x) => x.toString(16).padStart(2, "0")).join("");
}

class file {
    /*
    0   central file header signature   4 bytes  (0x02014b50)
    4   version made by                 2 bytes
    6   version needed to extract       2 bytes
    8   general purpose bit flag        2 bytes
    10  compression method              2 bytes
    12  last mod file time              2 bytes
    14  last mod file date              2 bytes
    16  crc-32                          4 bytes
    20  compressed size                 4 bytes  (压缩后大小)
    24  uncompressed size               4 bytes
    28  file name length                2 bytes  (文件名长度)
    30  extra field length              2 bytes  (扩展区长度)
    32  file comment length             2 bytes  (注释长度)
    34  disk number start               2 bytes
    36  internal file attributes        2 bytes
    38  external file attributes        4 bytes
    42  relative offset of local header 4 bytes  (文件存储区头结构偏移)

        file name (variable size)
        extra field (variable size)
        file comment (variable size)
    */

    constructor(buffer, offset) {
        this.buffer = buffer;

        // 头部固定数据段长度
        const fixed_len = 46;

        // 头结构视图
        const view = new DataView(buffer, offset, fixed_len);

        // 判断签名是否匹配，DataView Get 方法 true 为小端法
        this.match_sign = view.getInt32(0, true) === 0x02014b50;
        if (!this.match_sign) {
            return;
        }

        // 文件名长度
        let name_len = view.getInt16(28, true);
        // 文件名
        this.name = String.fromCharCode.apply(null, new Uint8Array(buffer, offset + fixed_len, name_len));
        // 计算本数据段总长，固定长度 + 文件名长度 + 扩展区长度 + 注释区长度
        this.info_len = fixed_len + name_len + view.getInt16(30, true) + view.getInt16(32, true);
        // 记录内容长度
        this.compressed_size = view.getInt32(20, true);

        // if (this.compressed_size > threshold) {
        //     console.log(this.compressed_size, this.name);
        // }

        // 内容 hash
        this.hash = "";

        // 文件区的头结构偏移
        this.header_offset = view.getInt32(42, true);
        // 文件区的头结构大小
        this.header_len = 0;
        // 内容
        this.data = null;
    }

    // 读取记录在存储区的文件内容 hash
    load_hash() {
        this.hash = get_hash_str(this.buffer, this.header_offset + this.header_len);
    }

    // 获取文件区文件头结构的长度
    parse_header_len() {
        /*
        Get local file header total length

        0   local file header signature     4 bytes  (0x04034b50)
        4   version needed to extract       2 bytes
        6   general purpose bit flag        2 bytes
        8   compression method              2 bytes
        10  last mod file time              2 bytes
        12  last mod file date              2 bytes
        14  crc-32                          4 bytes
        18  compressed size                 4 bytes
        22  uncompressed size               4 bytes
        26  file name length                2 bytes  (文件名长度)
        28  extra field length              2 bytes  (扩展区长度)

            file name (variable size)
            extra field (variable size)
        */
        let fixed_len = 30;
        const view = new DataView(this.buffer, this.header_offset, fixed_len);
        this.header_len = fixed_len + view.getInt16(26, true) + view.getInt16(28, true);
    }

    // 设置文件区文件头结构的真实偏移
    set_real_header_offset(offset) {
        this.header_offset = offset;
    }
}

class file_loader {
    constructor(hash, size) {
        this.hash = hash;
        this.size = size;
        this.onloaded = [];
        this.isloaded = false;
    }

    loaded(data) {
        for (const f of this.onloaded) {
            f.data = data;
        }
        this.isloaded = true;
    }
}

class downloader {
    constructor(zip_loader) {
        this.zip_loader = zip_loader;
        // 只是方便界面上显示文件信息
        this.file_loader = undefined;
        this.progress = 0;
    }

    next() {
        const f = this.zip_loader.need_downloads.pop();
        this.file_loader = f;
        if (f !== undefined) {
            let url = "blocks/" + f.hash
            if (this.zip_loader.base_url) {
                url = this.zip_loader.base_url + "/" + url;
            }
            download(url, (p) => {
                this.progress = p;
            })
                .then((data) => {
                    this.next();
                    this.insert_db(data, f);
                })
                .catch((error) => {
                    console.log(error);
                    this.zip_loader.download_state.error_num++;
                    this.next();
                });
        }
    }

    insert_db(data, file_loader) {
        idbKeyval
            .set(file_loader.hash, data)
            .then(() => {
                let st = this.zip_loader.download_state;
                file_loader.loaded(data);
                st.downloaded_num++;
                st.downloaded_size += file_loader.size;
            })
            .catch((error) => {
                // TODO: 重试下载 ？
                console.log(error);
                this.zip_loader.download_state.error_num++;
            });
    }
}

// 参考：https://zh.javascript.info/xmlhttprequest
function download(url, progress_callback) {
    return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();
        xhr.open("GET", url);
        xhr.responseType = "arraybuffer";
        xhr.send();

        xhr.onload = () => {
            if (xhr.status !== 200) {
                reject(new Error(`Error ${xhr.status}: ${xhr.statusText}`));
                return;
            }

            resolve(xhr.response);
        };

        xhr.onerror = function () {
            reject(new Error("Network Error"));
        };

        xhr.onprogress = (event) => {
            progress_callback(event.loaded / event.total);
        };
    });
}

class zip_loader {
    constructor(url) {
        this.url = url;
        let arr = url.split("/");
        if (url.startsWith("http")) {
            // 目前的规则，都是包在项目目录下，blocks 目录和项目目录同级
            this.base_url = arr.slice(0, -2).join("/");
        }
        this.browser_download_name = arr.slice(-2).join("/");
        this.name = arr[arr.length - 1];
        this.shrink_data = null;
        this.shrink_data_progress = 0;
        this.origin_hash = "";
        // files 是所有解析后对应的 zip 中的文件
        this.files = [];
        // 只所以会有 file loader，是因为 zip 中不同文件可能是相同的，hash 相同，不需要重复下载
        this.file_loaders = [];
        this.download_state = {
            total_num: 0,
            total_size: 0,
            load_cached_num: 0,
            load_cached_size: 0,
            downloaded_num: 0,
            downloaded_size: 0,
            error_num: 0,
        };
        this.max_downloader = 5;
        this.ticker = null;

        this.downloaders = Array.from({length: this.max_downloader}, () => new downloader(this));
        this.need_downloads = [];
    }

    // 开始下载精简版本 zip
    start() {
        download(this.url, (p) => {
            this.shrink_data_progress = p;
        })
            .then((data) => {
                this.shrink_data = data;
                this.parse();
            })
            .catch((error) => {
                console.log(error);
                alert("download shrink package error: " + error);
            });
    }

    // 解析精简版本 zip
    parse() {
        let buffer = this.shrink_data;

        // 抽取写在文件末尾的原始文件 hash
        let end = buffer.byteLength - hash_len;
        this.origin_hash = get_hash_str(buffer, end);

        // 去掉末尾 hash 部分
        buffer = buffer.slice(0, end);
        this.shrink_data = buffer;

        // 开始解析
        let loaders = {};

        let dir = this.parse_EOCD(buffer);
        this.files = this.parse_directory(buffer, dir.offset, dir.size);

        // 抽出大小，用于修正精简版 zip 中文件头的偏移
        let ex_size = 0;
        // 遍历所有文件待处理文件
        for (const f of this.files) {
            // 计算头结构修正偏移
            f.set_real_header_offset(f.header_offset - ex_size);
            // 获取头结构大小
            f.parse_header_len();

            // 加载内容 hash
            f.load_hash();

            // 根据内容 hash 创建下载器（ zip 内相同的文件只会下载一份 ）
            if (!loaders.hasOwnProperty(f.hash)) {
                loaders[f.hash] = new file_loader(f.hash, f.compressed_size);
            }
            loaders[f.hash].onloaded.push(f);

            // 修正头结构偏移
            ex_size += f.compressed_size - hash_len;
        }

        // 转为列表
        this.file_loaders = Object.values(loaders);

        // 统计下载量
        this.download_state.total_num = this.file_loaders.length;
        this.download_state.total_size = this.file_loaders.reduce((acc, cur) => acc + cur.size, 0);

        this.load_from_db(loaders);
    }

    load_from_db(loaders) {
        const db = idb.openDB('keyval-store', 1, {
            upgrade(db) {
                if (!db.objectStoreNames.contains('keyval')) {
                    db.createObjectStore('keyval');
                }
            },
        });

        db.then(async (db) => {
            let cursor = await db.transaction('keyval', 'readonly').store.openCursor();
            while (cursor) {
                if (loaders.hasOwnProperty(cursor.key)) {
                    loaders[cursor.key].loaded(cursor.value);
                    this.download_state.load_cached_num++;
                    this.download_state.load_cached_size += loaders[cursor.key].size;
                }
                cursor = await cursor.continue();
            }
            this.start_download();
        }).catch((error) => {
            alert(`Failed to open database: ${error}`);
        });
    }

    start_download() {
        this.need_downloads = this.file_loaders.filter(f => !f.isloaded)

        // 开始下载
        for (let i = 0; i < this.max_downloader; i++) {
            this.downloaders[i].next();
        }

        // 等待完成
        this.ticker = setInterval(() => {
            this.update();
        }, 40);
    }

    // 解析中央目录结束标记，返回中央目录偏移和大小
    parse_EOCD(buffer) {
        /*
        重点: **中央目录中文件信息是连续的，且其后紧跟结束标记（zip64 除外，本项目暂不支持 zip64）**
        因为中央目录结束标记中记录的中央目录偏移是针对文件头的编译
        所以精简版 zip 这个偏移无法命中，也无法计算（需要先解析中央目录）
        只能这样计算: 中央目录结束标记偏移 - 目录大小

        End of central directory record

        0   end of central dir signature    4 bytes  (0x06054b50)
        4   number of this disk             2 bytes
        6   number of the disk with the
            start of the central directory  2 bytes
        8   total number of entries in the
            central directory on this disk  2 bytes
        10  total number of entries in
            the central directory           2 bytes
        12  size of the central directory   4 bytes  (中央目录大小)
        16  offset of start of central
            directory with respect to
            the starting disk number        4 bytes
        20  .ZIP file comment length        2 bytes
        22  .ZIP file comment               (variable size)
        */

        // EOCD固定数据段长度
        const fixed_len = 22;
        // 起始搜索位置近似值
        let offset = buffer.byteLength - fixed_len;
        while (offset > 0) {
            const view = new DataView(buffer, offset, fixed_len);
            if (view.getInt32(0, true) !== 0x06054b50) {
                offset -= 1;
                continue;
            }
            let size = view.getInt32(12, true);
            return {
                size: size,
                offset: offset - size,
            };
        }
        return null;
    }

    // 遍历中央目录中的所有文件信息
    parse_directory(buffer, dir_offset, dir_size) {
        let file_infos = [];
        let offset = dir_offset;
        let end = dir_offset + dir_size;
        while (offset < end) {
            let f = new file(buffer, offset);
            // 过滤掉小于 4k 的文件
            if (f.compressed_size > threshold) {
                file_infos.push(f);
            }
            offset += f.info_len;
        }

        // 按偏移量排序（中央目录不保证顺序，但不会有两个文件共用存储，结构上就不支持）
        /*
        From Wikipedia Zip Format:
        The order of the file entries in the central directory 
        need not coincide with the order of file entries in the archive
        */
        file_infos.sort((a, b) => a.header_offset - b.header_offset);
        return file_infos;
    }

    // 检查下载/加载状态
    update() {
        // 下载完成, TODO: retry when error
        let state = this.download_state;
        if (state.load_cached_num + state.downloaded_num + state.error_num == state.total_num) {
            console.log("all done");
            clearInterval(this.ticker);
            setTimeout(() => {
                this.repack();
            }, 40);
        }
    }

    // 重组 zip 包
    repack() {
        let bytes = [];
        let hash = md5.create();

        function append(byte_range) {
            bytes.push(byte_range);
            if (!window.is_hybrid_app) {
                hash.update(byte_range);
            }
        }

        // 光标，记录上一次处理到的位置
        let cursor = 0;
        // 遍历所有文件待处理文件
        for (const f of this.files) {
            // 写入上一个处理位置到此头结构结尾的数据
            let offset = f.header_offset + f.header_len;
            append(new Uint8Array(f.buffer, cursor, offset - cursor));

            // 写入文件内容
            append(new Uint8Array(f.data));

            // 光标置于文件内容区末尾（精简版只需要跳过 hash 的长度）
            cursor = offset + hash_len;
        }

        append(new Uint8Array(this.shrink_data, cursor));

        if (window.is_hybrid_app) {
            this.send_to_hybird_app(bytes);
            return;
        }

        console.log(hash.hex());
        if (this.origin_hash !== hash.hex()) {
            alert("hash check error");
            return;
        }

        let fileBlob = new Blob(bytes);
        let a = document.createElement("a");
        a.download = this.browser_download_name;
        a.href = URL.createObjectURL(fileBlob);
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    send_to_hybird_app(bytes) {
        let xhr = new XMLHttpRequest();
        xhr.open("POST", `http://127.0.0.1:10018?file=${this.name}&hash=${this.origin_hash}`, true);
        xhr.onload = () => {
            if (xhr.status != 200) {
                alert(`send to hybird app error: ${xhr.status}: ${xhr.statusText}`);
            }
            console.log("send to hybird app success");
        };

        xhr.onerror = function () {
            alert("send to hybird app error");
        };

        xhr.send(new Blob(bytes));
        console.log("send to hybird app");
    }
}
