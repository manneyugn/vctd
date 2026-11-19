# VCTĐ Tra cứu

Công cụ đọc và tra cứu cho tiểu thuyết dài, chạy hoàn toàn trong trình duyệt —
không máy chủ ứng dụng, không tài khoản, không build step.

Dựng cho **Vạn Cổ Thần Đế** (4.211 chương, 11,8 triệu từ), nhưng pipeline không
gắn với tác phẩm nào: đưa vào thư mục chương dạng text là chạy được.

## Có gì

| Tab | Làm gì |
| --- | --- |
| Đọc truyện | Tóm tắt AI đầu mỗi chương, 3 nền, chỉnh cỡ chữ và độ rộng, nhớ vị trí đọc, **đọc offline** |
| Mục lục | Lọc tức thì theo tên hoặc số chương |
| Tra cứu | 5.420 thực thể: số lần nhắc, biểu đồ mật độ, dòng thời gian, thực thể đi cùng, trích dẫn |
| Wiki | Duyệt theo loại, ngưỡng hiển thị để lọc mảnh vụn |
| Chat | Hỏi đáp 6 bước có dẫn nguồn chương (Gemini hoặc máy chủ LLM riêng) |
| Hiệu đính | Nhật ký các vị trí đã chuẩn hoá từ bản gốc |

## Chạy

```bash
cd app
./run.sh                      # http://127.0.0.1:8731
```

Cần chạy qua HTTP — mở thẳng `index.html` sẽ bị trình duyệt chặn vì CORS.

## Pipeline

```bash
python3 pipeline/build_corpus.py       # chương thô → shard gzip + nhật ký hiệu đính
python3 pipeline/extract_entities.py   # tìm ứng viên tên riêng
python3 pipeline/refine_entities.py    # nuốt mảnh vụn, gộp bí danh, lọc từ chức năng
python3 pipeline/build_index.py        # postings, đồng xuất hiện, trích dẫn

bash tom-tat.sh 4                      # tóm tắt từng chương bằng LLM
python3 pipeline/chuan_hoa_ten.py      # chuẩn hoá tên riêng trong tóm tắt
python3 pipeline/phan_loai.py          # phân loại bằng mẫu ngữ cảnh
bash phan-loai.sh 4                    # phân loại phần còn lại bằng LLM
SEO_BASE_URL=... python3 pipeline/build_public.py  # đóng gói để deploy + trang SEO
```

Máy chủ LLM cấu hình qua biến môi trường, xem `app/.env.example`. Bất kỳ endpoint
nào theo chuẩn OpenAI `/v1/chat/completions` đều dùng được.

## Deploy (Vercel)

`build_public.py` sinh `app/public/` (không commit): SPA không shard + trang
tinh cho máy tìm và AI engine — một HTML cho từng chương (4.211) và từng thực
thể đủ lớn (1.390), `sitemap.xml` + `robots.txt`, và `llms.txt`/`llms-full.txt`.
Trang SEO chỉ mang metadata và tóm tắt, không có text nguyên văn.

```bash
cd app/public
vercel --prod          # hoặc nhập repo: Root Directory = app/public, Build Command trống
```

Không có build step — Vercel phát hiện site tĩnh; `vercel.json` bật `cleanUrls`
và header `*.gz`. Đặt `SEO_BASE_URL` đúng domain cuối (canonical và sitemap đọc
từ đó), build lại, deploy lại.

## Vài thứ học được khi làm

**Nhận diện tên riêng trong bản convert.** Bản convert viết hoa lung tung nên quy
tắc viết hoa thông thường vô dụng. Tín hiệu cứu cánh là *tỉ lệ viết hoa giữa câu*:
tên riêng rơi vào 0,68–0,96 còn cụm từ thông dụng nằm ở 0,00–0,08 — tách gần như
tuyệt đối. Kết hợp với độ kết dính n-gram (PMI) và hậu tố Hán-Việt.

**Vị trí quyết định nghĩa.** Không chặn được một âm tiết ở mọi vị trí: `các` đứng
cuối là 閣 (gác) nên `phi thiên các` là thế lực thật, nhưng `các hạ` đứng đầu là
đại từ. Tương tự `bổn nguyên` (本源) là thuật ngữ còn `bổn hoàng` là "trẫm".

**Sửa chính tả tên riêng không tự động hoá được.** `Thiên Đỉnh` (1 trong Cửu Đỉnh,
213 lần) chỉ lệch 1 ký tự so với `Thiên Đình` (địa danh, 5.749 lần) nhưng là hai
thực thể khác hẳn — trong khi `Trương Ngược Trần` xuất hiện 1.685 lần mà vẫn chỉ
là lỗi gõ. Không ngưỡng tần suất hay khoảng cách ký tự nào tách được chúng, nên
chỉ các cặp trong `pipeline/name-overrides.json` mới được áp dụng.

**Model reasoning cần nới chỗ, không phải gọi lại.** `finish_reason=length` với
content rỗng nghĩa là model hết chỗ giữa lúc đang "nghĩ"; gọi lại y nguyên chỉ lặp
lại đúng thất bại đó. `summarize.py` nới dần 8000 → 32000 qua các lượt thử, còn
`phan_loai_ai.py` thì chia đôi lô để model có ít thứ phải nghĩ hơn.

**Hậu tố phủ quyết ngữ cảnh.** Khi phân loại, `Thiên Đình Giới` vẫn là địa danh dù
câu văn nói về nó như một nhân vật — bằng chứng hình thái mạnh hơn mẫu ngữ cảnh.
