class file {
    /*
    0	4	local file header signature	文件头标识(固定值0x04034b50)
    4	2	version needed to extract	解压时遵循ZIP规范的最低版本
    6	2	general purpose bit flag	通用标志位
    8	2	compression method	压缩方式
    10	2	last mod file time	最后修改时间（MS - DOS格式）
    12	2	last mod file date	最后修改日期（MS - DOS格式）
    14	4	crc - 32	冗余校验码
    18	4	compressed size	压缩后的大小
    22	4	uncompressed size	未压缩之前的大小
    26	2	file name length	文件名长度（n）
    28	2	extra field length	扩展区长度（m）
    30	n	file name	文件名
    30+n m	extra field	扩展区
    */

    constructor(buffer, offset) {
        this.buffer = buffer;
        this.offset = offset;

        // 头部固定数据段长度 30
        const fixed_len = 30;

        // 头结构视图
        const view = new DataView(buffer, offset, fixed_len);

        // 判断是否是文件头，DataView Get 方法 true 为小端法
        this.is_file = view.getInt32(0, true) === 0x04034b50;

        if (!this.is_file) {
            return;
        }

        // 解析文件名，从头结构末尾开始
        this.name_len = view.getInt16(26, true);
        // this.file_name = String.fromCharCode.apply(null, new Uint8Array(buffer, offset + fixed_len, name_len));

        // 计算头结构总长，头固定长 + 文件名长 + 扩展区长
        this.head_len = fixed_len + this.name_len + view.getInt16(28, true);
        // 记录内容长度
        this.data_len = view.getInt32(18, true);

        // 读取 hash
        this.hash_len = 16;
        const hash_view = new Uint8Array(buffer, this.offset + this.head_len, this.hash_len);
        this.hash = [...hash_view].map((x) => x.toString(16).padStart(2, "0")).join("");

        // 内容
        this.data = null;
    }
}

const State = {
    Init: 0,
    NeedDownload: 1,
    Downloading: 2,
    Success: 3,
    Fail: 4,
};

const threshold = 4096;

class file_loader {
    constructor(hash, size) {
        this.hash = hash;
        this.size = size;
        this.timeout = 0; // TODO
        this.state = State.Init;
        this.checked_db = false;
        this.onloaded = [];
    }

    load_from_db() {
        idbKeyval.get(this.hash).then((data) => {
            if (data === undefined) {
                this.state = State.NeedDownload;
            } else {
                this.loaded(data);
            }
        });
    }

    download() {
        this.state = State.Downloading;

        fly.get("tmp/" + this.hash, null, {
            responseType: "arraybuffer",
        })
            .then((response) => {
                this.insert_db(response.data);
            })
            .catch((error) => {
                console.log(error);
                this.state = State.Fail;
            });
    }

    insert_db(data) {
        idbKeyval
            .set(this.hash, data)
            .then(() => {
                this.loaded(data);
            })
            .catch((error) => {
                console.log(error);
                this.state = State.Fail;
            });
    }

    loaded(data) {
        for (const f of this.onloaded) {
            f.data = data;
        }
        this.state = State.Success;
    }
}

class zip_loader {
    constructor(path, callback) {
        this.path = path;
        this.callback = callback;
        this.shrink_data = null;
        this.files = [];
        this.file_loaders = [];
        this.others_offset = 0;
        this.max_downloader = 5;
        this.ticker = null;
    }

    start() {
        fly.get(this.path, null, {
            responseType: "arraybuffer",
        })
            .then((response) => {
                this.callback("shrink zip loaded");
                this.shrink_data = response.data;
                this.parse();
            })
            .catch((error) => {
                this.callback("load shrink zip error");
                console.log(error);
                alert(error);
            });
    }

    parse() {
        let buffer = this.shrink_data;
        let offset = 0;
        let loaders = {};

        // 遍历所有头结构
        while (true) {
            let f = new file(buffer, offset);

            if (!f.is_file) {
                break;
            }

            this.files.push(f);

            if (f.data_len < threshold) {
                // 小文件就在 shrink zip 里，无需下载，直接返回下一个的偏移
                offset = f.offset + f.head_len + f.data_len;
            } else {
                // 根据内容 hash 创建下载器（ zip 内相同的文件只会下载一份 ）
                if (!loaders.hasOwnProperty(f.hash)) {
                    loaders[f.hash] = new file_loader(f.hash, f.data_len);
                }
                loaders[f.hash].onloaded.push(f);

                // 下一个
                offset = f.offset + f.head_len + f.hash_len;
            }
        }

        // 转为列表
        this.file_loaders = Object.values(loaders);

        // 记录非内容区偏移
        this.others_offset = offset;

        // 开始批量加载，没秒 25 帧
        this.ticker = setInterval(() => {
            this.update();
        }, 40);
    }

    update() {
        // 扫描下载/加载状态
        let need_download = [];
        let loaded = 0;
        let error = 0;
        let downloading = 0;
        for (const l of this.file_loaders) {
            if (l.state === State.Init) {
                l.load_from_db();
            } else if (l.state === State.NeedDownload) {
                need_download.push(l);
            } else if (l.state === State.Downloading) {
                downloading++;
            } else if (l.state === State.Success) {
                loaded++;
            } else if (l.state === State.Fail) {
                error++;
            }
        }

        let msg = "downloading " + loaded + "/" + this.file_loaders.length;
        if (error > 0) {
            msg += " , Errors " + error;
        }
        this.callback(msg);

        // 添加下载
        for (let i = 0; i < Math.min(this.max_downloader - downloading, need_download.length); i++) {
            need_download[i].download();
        }

        // 下载完成
        if (loaded === this.file_loaders.length) {
            console.log("all done");
            clearInterval(this.ticker);
        }
    }
}
