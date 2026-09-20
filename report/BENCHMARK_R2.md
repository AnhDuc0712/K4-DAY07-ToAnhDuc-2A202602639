# R2 · Benchmark truy xuất chính sách hậu mãi

Bộ benchmark này dùng đúng 5 query cho corpus trong `data/ecommerce/`. Gold answer chỉ sử dụng thông tin đã có trong tài liệu đã thu thập; không dùng kiến thức bên ngoài hoặc suy đoán chính sách.

## 1. Query và gold answer

### Query 1 — Thời hạn xử lý yêu cầu của người bán

**Query:** Người bán TikTok Shop phải xem xét yêu cầu trả hàng/hoàn tiền của người mua trong bao lâu? Nếu không xử lý đúng hạn thì điều gì xảy ra?

**Gold answer:** Người bán phải xem xét yêu cầu trong vòng **1 ngày theo lịch** kể từ khi nhận được yêu cầu. Nếu người bán không thực hiện hành động trong thời gian quy định, yêu cầu có thể được **phê duyệt tự động**.

**Metadata filter:** `{"platform": "tiktok_shop", "audience": "seller", "category": "return_refund"}`

**Nguồn kiểm chứng:** `data/ecommerce/tiktok-shop-return-refund-seller.md`, mục **Thời hạn xem xét yêu cầu**.

### Query 2 — Thời hạn người mua gửi hàng trả

**Query:** Sau khi yêu cầu trả hàng trên TikTok Shop được phê duyệt, người mua có bao nhiêu thời gian để gửi sản phẩm? Điều gì xảy ra nếu gửi trễ?

**Gold answer:** Người mua có **10 ngày theo lịch** sau khi yêu cầu trả hàng được phê duyệt để vận chuyển sản phẩm trả hàng. Nếu không gửi trong thời hạn này, yêu cầu sẽ bị **đóng và không thực hiện hoàn tiền**.

**Metadata filter:** `{"platform": "tiktok_shop", "audience": "seller", "category": "return_refund"}`

**Nguồn kiểm chứng:** `data/ecommerce/tiktok-shop-return-refund-seller.md`, mục **Thời hạn người mua gửi hàng trả**.

### Query 3 — Hoàn tiền toàn bộ và hoàn tiền một phần

**Query:** Trên TikTok Shop, hoàn tiền toàn bộ khác hoàn tiền một phần ở điểm nào đối với khả năng người mua gửi yêu cầu hậu mãi tiếp theo?

**Gold answer:** Nếu người bán **hoàn tiền toàn bộ**, người mua không thể gửi thêm yêu cầu hậu mãi cho đơn hàng đó. Nếu **hoàn tiền một phần**, người mua vẫn có thể gửi yêu cầu hậu mãi; tổng số tiền hoàn sau đó không vượt quá giá trị đơn hàng ban đầu.

**Metadata filter:** `{"platform": "tiktok_shop", "audience": "seller", "category": "return_refund"}`

**Nguồn kiểm chứng:** `data/ecommerce/tiktok-shop-refund-proposal-seller.md`, mục **Khác nhau giữa hoàn tiền toàn bộ và một phần**.

### Query 4 — Điều kiện bảo hành và trách nhiệm người bán trên Shopee

**Query:** Người bán trên Shopee có trách nhiệm gì về bảo hành, và người mua cần đáp ứng những điều kiện cơ bản nào để được bảo hành?

**Gold answer:** Người bán phải tiếp nhận bảo hành theo chính sách của người bán và/hoặc nhà sản xuất, đồng thời phải đăng thông tin bảo hành trong phần mô tả sản phẩm/dịch vụ. Các điều kiện cơ bản gồm: sản phẩm còn thời hạn bảo hành, còn tem hoặc phiếu bảo hành, và lỗi kỹ thuật không do người mua gây ra.

**Metadata filter:** `{"platform": "shopee", "category": "warranty"}`

**Nguồn kiểm chứng:** `data/ecommerce/shopee-warranty-policy-both.md`, mục **Trách nhiệm của người bán** và **Điều kiện bảo hành cơ bản**.

### Query 5 — Thời gian xử lý và hoàn tiền của Shopee

**Query:** Khi người mua gửi yêu cầu trả hàng/hoàn tiền trên Shopee, yêu cầu thường được xử lý trong bao lâu và tiền được hoàn trong bao lâu nếu yêu cầu được chấp nhận?

**Gold answer:** Yêu cầu thường được xử lý trong khoảng **3–5 ngày làm việc**. Nếu được chấp nhận, tiền được hoàn trong **1–14 ngày làm việc**, tùy thuộc vào phương thức thanh toán.

**Metadata filter:** `{"platform": "shopee", "audience": "buyer", "category": "return_refund"}`

**Nguồn kiểm chứng:** `data/ecommerce/shopee-return-refund-guide-buyer.md`, mục **Thời gian xử lý và hoàn tiền**.

## 2. Tự kiểm gold answer

| # | Gold answer có trong tài liệu? | Chi tiết đã đối chiếu | Kết quả |
|---|---|---|---|
| 1 | Có | `1 ngày theo lịch`; không hành động có thể được phê duyệt tự động | PASS |
| 2 | Có | `10 ngày theo lịch`; trễ thì yêu cầu bị đóng và không hoàn tiền | PASS |
| 3 | Có | Hoàn toàn bộ chặn yêu cầu tiếp theo; hoàn một phần vẫn cho phép yêu cầu và tổng hoàn không vượt giá trị đơn | PASS |
| 4 | Có | Trách nhiệm đăng thông tin/tiếp nhận bảo hành; 3 điều kiện bảo hành cơ bản | PASS |
| 5 | Có | Xử lý `3–5 ngày làm việc`; hoàn tiền `1–14 ngày làm việc` | PASS |

## 3. Coverage

- Có 3 query dành cho `seller` và 1 query dành cho `buyer` cần metadata filter.
- Có 1 query về `warranty` và 4 query về `return_refund`.
- Có câu hỏi về thời hạn, quy trình, điều kiện, trách nhiệm và trạng thái xử lý.
- Không tạo query về nội dung không có trong corpus.
