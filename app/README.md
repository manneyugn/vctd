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
| Tra cứu | Tìm trong 5.878 thực thể: số lần nhắc, chương đầu/cuối, biểu đồ mật độ, chương tập trung nhất, **dòng thời gian**, thực thể đi cùng, trích dẫn |
| Wiki | Duyệt toàn bộ thực thể, lọc theo loại |
| Chat | Hỏi đáp 6 bước có dẫn nguồn chương (Gemini hoặc máy chủ LLM riêng) |
| Hiệu đính | Nhật ký 15.346 vị trí đã chuẩn hoá từ bản convert |

Phím tắt khi đọc: `←` `→` chuyển chương · `M` mục lục · `A` tuỳ chỉnh hiển thị.

## Pipeline dữ liệu

Chạy lại theo thứ tự khi có dữ liệu nguồn mới:

```bash
python3 pipeline/build_corpus.py      # chương thô  → shard gzip + nhật ký hiệu đính
python3 pipeline/extract_entities.py  # tìm ứng viên tên riêng          (~30 giây)
python3 pipeline/refine_entities.py   # nuốt mảnh vụn, gộp bí danh
python3 pipeline/build_index.py       # postings, đồng xuất hiện, trích dẫn (~15 giây)

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

### Phân loại thực thể

`phan_loai.py` phân loại lại bằng tóm tắt thay vì bản convert, vì tóm tắt đúng ngữ
pháp và viết hoa chuẩn nên mẫu ngữ cảnh chạy sạch hơn. Nguyên tắc: **hậu tố
Hán-Việt phủ quyết ngữ cảnh** — "Thiên Đình Giới" vẫn là địa danh dù câu văn nói
về nó như một nhân vật. Ngữ cảnh chỉ được quyết với các mục đang nằm ở nhóm "Khác".

### Sửa tay kết quả

Sửa `pipeline/name-overrides.json` cho tên riêng, hoặc `web/data/entities.json.gz`
rồi chạy lại `build_index.py` cho phân loại.

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