# Vạn Cổ Thần Đế · Tra cứu

Công cụ đọc và tra cứu chạy hoàn toàn trong trình duyệt, không cần máy chủ ứng dụng,
không cần tài khoản. Dữ liệu nằm trong `web/data/`.

## Chạy

```bash
./run.sh          # mặc định cổng 8731
./run.sh 9000     # đổi cổng
```

Mở http://127.0.0.1:8731 — cần chạy qua HTTP, mở trực tiếp file `index.html`
sẽ bị trình duyệt chặn vì chính sách CORS.

## Tính năng

| Tab | Làm gì |
|---|---|
| Đọc truyện | 4.211 chương, **tóm tắt AI đầu mỗi chương**, chuyển chương liền mạch, cỡ chữ / giãn dòng / độ rộng / 3 nền, nhớ vị trí đọc, URL riêng cho từng chương (`#doc/1234`) |
| Mục lục | Lọc tức thì theo tên hoặc số chương |
| Tra cứu | Tìm trong 5.162 thực thể: số lần nhắc, chương đầu/cuối, biểu đồ mật độ, chương tập trung nhất, **dòng thời gian**, thực thể đi cùng, trích dẫn |
| Wiki | Duyệt toàn bộ thực thể, lọc theo loại |
| Chat | Hỏi đáp 6 bước có dẫn nguồn chương (Gemini hoặc máy chủ LLM riêng) |
| Hiệu đính | Nhật ký 153.835 chỗ sửa ở 4.198 chương: dấu câu, chữ Hán sót, ghi chú LLM lẫn vào truyện, chính tả, viết hoa, 27.120 chỗ sửa tên riêng |

Phím tắt khi đọc: `←` `→` chuyển chương · `M` mục lục · `A` tuỳ chỉnh hiển thị.

## Pipeline dữ liệu

Chạy lại theo thứ tự khi có dữ liệu nguồn mới:

```bash
python3 pipeline/build_corpus.py      # chương thô → hiệu đính → shard gzip + nhật ký hiệu đính
python3 pipeline/extract_entities.py  # tìm ứng viên tên riêng          (~30 giây)
python3 pipeline/refine_entities.py   # nuốt mảnh vụn, gộp bí danh
python3 pipeline/build_index.py       # postings, đồng xuất hiện, trích dẫn (~15 giây)
python3 pipeline/giu_phan_loai.py <index cũ>   # giữ loại thực thể + bộ lọc đã duyệt từ index cũ

bash tom-tat.sh 4                     # tóm tắt từng chương bằng LLM     (~12 giờ)
python3 pipeline/chuan_hoa_ten.py     # chuẩn hoá tên riêng trong tóm tắt
python3 pipeline/phan_loai.py         # phân loại lại thực thể bằng tóm tắt (~16 giây)
```

### Cách nhận diện tên riêng

Bản convert không viết hoa tên riêng nhất quán nên không dùng được quy tắc viết hoa
thông thường. Pipeline kết hợp ba tín hiệu, không dùng AI:

1. **Độ kết dính n-gram (PMI)** — "côn lôn" hầu như chỉ xuất hiện cạnh nhau.
2. **Tỉ lệ viết hoa giữa câu** — đây là tín hiệu quyết định: tên riêng rơi vào
   khoảng 0,68–0,96 còn cụm từ thông dụng ("vô cùng", "thời gian") nằm ở 0,00–0,08.
   Ngưỡng cắt đặt ở 0,30.
3. **Mẫu ngữ cảnh Hán-Việt** — hậu tố `…giới`, `…tông`, `…đế`, và động từ đứng sau
   tên (nói, cười, nhìn…) để phân biệt nhân vật với địa danh.

Sau đó bước tinh lọc nuốt mảnh vụn ("lôn giới" ⊂ "côn lôn giới"), gộp tên rút gọn
thành bí danh, và loại các cụm "tên riêng + động từ".

### Tóm tắt từng chương

`tom-tat.sh` gọi một máy chủ LLM theo chuẩn OpenAI. Nó tự lo chứng chỉ (máy chủ nội
bộ thường ký bằng CA riêng, mà Python không đọc keychain hệ thống như curl), ghi
checkpoint sau từng chương nên dừng giữa chừng không mất gì, và nới `max_tokens`
dần 8000 → 32000 qua các lượt thử lại. Lần nới này là mấu chốt với model reasoning:
`finish_reason=length` nghĩa là model hết chỗ giữa lúc đang "nghĩ", nên gọi lại y
nguyên chỉ lặp lại đúng thất bại đó.

Bản tóm tắt nào không đạt (quá ngắn, quá dài, lẫn văn bản suy nghĩ, không có dấu
tiếng Việt) bị coi là thất bại và chạy lại, không ghi vào checkpoint. Chạy
`--clean` để dọn checkpoint cũ, `--probe` để thử kết nối.

### Chuẩn hoá tên riêng: vì sao cần người duyệt

Tóm tắt kế thừa lỗi gõ tên từ bản convert, và LLM đôi khi dịch nghĩa âm Hán-Việt
("Lâm Phi" thành "Rừng Phi"). `chuan_hoa_ten.py` sửa hai loại đó, nhưng xử lý
chúng rất khác nhau:

**Dịch nghĩa — tự động.** Sinh biến thể bằng cách thay âm tiết trong tên chuẩn
bằng nghĩa thuần Việt rồi khớp chính xác. An toàn theo thiết kế.

**Sai chính tả — phải duyệt tay.** Chỉ áp dụng các cặp liệt kê trong
`pipeline/name-overrides.json`. Lý do: không có ngưỡng tự động nào đúng được.
"Thiên Đỉnh" (1 trong Cửu Đỉnh, 213 lần trong truyện) chỉ lệch 1 ký tự so với
"Thiên Đình" (địa danh, 5.749 lần) nhưng là hai thực thể khác hẳn — trong khi
"Trương Ngược Trần" xuất hiện tới 1.685 lần mà vẫn chỉ là lỗi gõ. Tần suất không
tách được chúng, khoảng cách ký tự cũng không. Cặp chưa duyệt được ghi vào
`name-proposals.json` chứ không tự sửa.

### Hiệu đính bản dịch

Bản dịch máy có nhiều lỗi ngoài tên riêng. `build_corpus.py` cho mọi chương đi qua
`pipeline/hieu_dinh.py` trước khi đóng shard, theo thứ tự:

1. **Dấu câu kiểu Trung** (`，。「」…`) → dấu Việt; khoảng trắng quanh dấu và ngoặc kép.
2. **Ghi chú LLM lẫn vào truyện** (`ghi_chu_llm.py`): "(sửa thành: X)", "à nhầm",
   mũi tên "A -> B", glossary, lộ prompt, quảng cáo nguồn. Chỉ giữ vế đúng khi chắc chắn;
   chỗ không tự xử lý được nằm trong `hieu-dinh/sua-tay.json`.
3. **Chữ Hán sót** → âm Hán-Việt (`hieu-dinh/han-viet.json`, `tu-han.json`), chọn âm
   bằng bigram toàn truyện; chữ Thái/Hàn/Nhật/Nga/Ả Rập lạc vào → loại hoặc thay.
4. **Tên riêng và chính tả** theo `pipeline/name-overrides.json` + `hieu-dinh/chinh-ta.json`.
5. **Viết hoa** tên riêng và đầu câu, nối đoạn bị ngắt, sửa tiêu đề chương.

Mỗi chỗ sửa được ghi vào `clean-log.json.gz` (tab Hiệu đính trong app).

### Kiểm tra tên riêng giữa các chương

Bản dịch do LLM làm từng đoạn nên cùng một nhân vật bị viết nhiều kiểu, và LLM hay
**dịch nghĩa** chữ Hán thay vì đọc âm (韩湫 → "Hàn Thấp Trũng Hồ Nước", 罗盘 → "Lưới Bàn",
鬼头鞭 → "Quỷ Đầu Roi") hoặc **thay nhầm sang nhân vật khác** (c645 "Trì Côn Lôn" thực ra
là Hàn Thu). Các bộ dò, chạy sau khi có shard:

```bash
python3 pipeline/ten_theo_chuong.py index   # index tên từng chương → hieu-dinh/ten-theo-chuong.json.gz
python3 pipeline/ten_theo_chuong.py do      # biến thể khác 1 âm tiết so với tên ở chương ±12
python3 pipeline/ten_lac_thoi.py            # tên xuất hiện trước khi nhân vật ra mắt
python3 pipeline/ten_la.py                  # tên lẻ loi (kể cả chỉ 1 lần) gần giống nhân vật lân cận
python3 pipeline/ten_dich_nghia.py          # nhân vật vắng chương n + cụm cùng họ chứa từ thuần Việt
python3 pipeline/ten_khop_tu.py             # cụm lạ chia 1–2 từ với tên ở chương ±5, độ dài tùy ý
python3 pipeline/doi_chieu_wiki.py          # đối chiếu với danh mục tên lấy từ wiki
```

Các bộ dò chỉ đưa ra ứng viên (`hieu-dinh/ten-*.json`); quyết định sửa luôn qua người
duyệt, dựa trên **wiki** (`hieu-dinh/wiki-ten.txt`: ~740 tên tiếng Trung lấy từ Baidu Baike,
newton.com.tw, maigoo…, chuyển sang Hán-Việt bằng `han-viet.json`) và **ngữ cảnh các
chương lân cận**. Nguyên tắc:

- Tên nhân vật/công pháp/bảo vật theo **đúng âm Hán-Việt** của chữ gốc, không theo nghĩa
  và không theo cách viết đông nhất nếu cách đó là dịch nghĩa (橙月星使 → Tranh Nguyệt
  Tinh Sứ, 狩天大宴 → Thú Thiên Đại Yến, 天姥 → Thiên Mụ, 孟凰娥 / 孟凰妳 → Mạnh Hoàng Nga /
  Mạnh Hoàng Nhĩ — hai chị em song sinh mà bản dịch trộn làm một).
- Không có trên wiki và không có trong ngữ cảnh lân cận thì coi là lỗi dịch/hallu của tên
  nhân vật gần đó; không tìm ra gốc thì để nguyên.
- Cụm có nghĩa thật (Thiên Viên Vô Khuyết = cảnh giới 天圆无缺, Thiên Đỉnh ∈ Cửu Đỉnh) giữ nguyên.

`name-overrides.json` có ba loại quy tắc:

| Khoá | Khớp | Dùng khi |
|---|---|---|
| `duyet` | không phân biệt hoa thường | biến thể không bao giờ là từ thường |
| `duyet_viet_hoa` | chỉ dạng Viết Hoa Từng Chữ | biến thể trùng từ thường ("Trì Yêu" vs "duy trì") |
| `theo_chuong` | chỉ trong các chương liệt kê | tên đúng ở chỗ này nhưng sai ở chỗ khác (Thiên Nô 天奴 trước c2600 / Thiên Mụ 天姥 sau đó) |

Khi đổi tên chuẩn, cập nhật cả các quy tắc cũ đang trỏ về tên cũ, nếu không chạy lại
`build_corpus.py` sẽ đảo ngược. Danh sách đã áp theo từng đợt nằm trong
`hieu-dinh/*-da-ap*.txt` và `ten-da-duyet.json`.

### Phân loại thực thể

`phan_loai.py` phân loại lại bằng tóm tắt thay vì bản convert, vì tóm tắt đúng ngữ
pháp và viết hoa chuẩn nên mẫu ngữ cảnh chạy sạch hơn. Nguyên tắc: **hậu tố
Hán-Việt phủ quyết ngữ cảnh** — "Thiên Đình Giới" vẫn là địa danh dù câu văn nói
về nó như một nhân vật. Ngữ cảnh chỉ được quyết với các mục đang nằm ở nhóm "Khác".

### Sửa tay kết quả

Sửa `pipeline/name-overrides.json` cho tên riêng (xem bảng ở trên), `hieu-dinh/sua-tay.json`
cho đoạn văn cụ thể, hoặc `web/data/entities.json.gz` rồi chạy lại `build_index.py` +
`giu_phan_loai.py` cho phân loại. Sửa xong chạy lại `build_corpus.py` và copy
`web/data/*` (trừ shard) sang `public/data/`.

## Chat (tuỳ chọn)

Luồng 6 bước, hiện tiến trình ngay trên bong bóng chat:

1. Nhận diện thực thể trong câu hỏi
2. Tra chỉ mục lấy postings, bí danh, mốc đầu/cuối
3. Xếp hạng chương, thưởng cho chương có nhiều thực thể cùng xuất hiện
4. Dựng dòng thời gian từ tóm tắt
5. Thu thập bằng chứng: tóm tắt các chương liên quan + nguyên văn 2 chương sát nhất
6. AI tổng hợp, mọi ý kèm `c.<số chương>` bấm được

Bằng chứng chính là tóm tắt chứ không phải toàn văn, nên phủ trọn 4.211 chương mà
không phải tải thêm shard nào. Ba lượt hỏi đáp gần nhất được đưa vào prompt.

Chọn nguồn AI trong ⚙ Cài đặt:

- **Gemini** — key lấy ở https://aistudio.google.com/apikey
- **Máy chủ riêng** — bất kỳ endpoint OpenAI-compatible nào. Máy chủ phải bật CORS
  cho origin của trang, vì đây là trình duyệt gọi trực tiếp.

Không cấu hình gì thì Chat vẫn trả về tra cứu thuần: thực thể, dòng thời gian,
chương liên quan. Chạy hoàn toàn offline.

## Đóng gói và deploy

```bash
SEO_BASE_URL=https://<domain> python3 pipeline/build_public.py
```

Đưa `web/` ra `public/`: bỏ các shard chương (bản tra cứu không cần — đã có
tóm tắt), viết lại `chapters.json` sang mode tra cứu (nguồn webnovel.vn), và
sinh phần SEO/GEO:

| URL | Nội dung |
|---|---|
| `/` | SPA như `web/`; `index.html` được thêm meta + canonical + JSON-LD |
| `/truyen/` | Trang tổng quan: 4.211 chương, 11,8 triệu từ |
| `/chuong/N/` | Tiêu đề, tổng từ, top thực thể, tóm tắt AI, nút mở trong app |
| `/wiki/<slug>/` | Định nghĩa một câu: loại, số lần nhắc, mốc chương, trích dẫn, đi liền với (1.390 thực thể qua ngưỡng) |
| `/sitemap.xml` | Index 3 sitemap con, `robots.txt` kèm dòng `Sitemap:` |
| `/llms.txt`, `/llms-full.txt` | Bảng chỉ mục và toàn bộ ngữ liệu (tóm tắt + định nghĩa) cho AI engine |

Deploy Vercel — không build step, trỏ thẳng vào `public/`:

```bash
cd public
vercel --prod        # hoặc repo GitHub: Root Directory = app/public, Build Command trống
```

`vercel.json` bật `cleanUrls` và header octet-stream cho `*.gz`; `llms-full.txt`
~2.5 MB tự được Vercel nén khi serve. Không có text nguyên văn trong bản
deploy, mọi trang ghi nguồn và tác giả.