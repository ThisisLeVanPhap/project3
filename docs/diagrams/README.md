# Use Case Diagrams

Thư mục này chứa các biểu đồ use case của hệ thống chatbot tư vấn bán hàng nội thất.

## Danh sách file

1. **usecase-tong-quat.puml** - Biểu đồ use case tổng quát
2. **usecase-tu-van-san-pham.puml** - Phân rã: Tư vấn sản phẩm theo cửa hàng
3. **usecase-quan-ly-chatbot-kb.puml** - Phân rã: Quản lý chatbot và knowledge base
4. **usecase-tham-chieu-gia.puml** - Phân rã: Tham chiếu giá
5. **usecase-quan-ly-hoi-thoai-yeu-cau.puml** - Phân rã: Quản lý hội thoại và yêu cầu mua hàng

## Render sang PNG/PDF

### Sử dụng PlantUML CLI

**Cài đặt PlantUML:**
```bash
# Windows (với Chocolatey)
choco install plantuml

# macOS (với Homebrew)
brew install plantuml

# Linux (Ubuntu/Debian)
sudo apt-get install plantuml

# Hoặc download JAR từ https://plantuml.com/download
```

**Render tất cả file sang PNG:**
```bash
cd docs/diagrams
plantuml *.puml
```

**Render sang PNG với độ phân giải cao:**
```bash
plantuml -DPLANTUML_LIMIT_SIZE=8192 *.puml
```

**Render sang SVG (vector, chất lượng tốt nhất):**
```bash
plantuml -tsvg *.puml
```

**Render sang PDF:**
```bash
plantuml -tpdf *.puml
```

**Render một file cụ thể:**
```bash
plantuml usecase-tong-quat.puml
```

### Sử dụng PlantUML Server (online)

Upload file .puml lên https://www.plantuml.com/plantuml/uml/ hoặc sử dụng VS Code extension.

### Sử dụng VS Code

1. Cài extension: **PlantUML** (jebbs.plantuml)
2. Mở file .puml
3. Nhấn `Alt+D` để preview
4. Click chuột phải → "Export Current Diagram" → chọn format (PNG/SVG/PDF)

### Sử dụng Docker

```bash
# Pull PlantUML Docker image
docker pull plantuml/plantuml

# Render tất cả file trong thư mục hiện tại
docker run --rm -v $(pwd):/data plantuml/plantuml *.puml
```

## Chèn vào LaTeX

### Sử dụng PNG
```latex
\begin{figure}[H]
\centering
\includegraphics[width=0.9\textwidth]{diagrams/usecase-tong-quat.png}
\caption{Biểu đồ use case tổng quát của hệ thống chatbot tư vấn bán hàng nội thất}
\label{fig:usecase-overview}
\end{figure}
```

### Sử dụng PDF (chất lượng tốt hơn)
```latex
\begin{figure}[H]
\centering
\includegraphics[width=0.9\textwidth]{diagrams/usecase-tong-quat.pdf}
\caption{Biểu đồ use case tổng quát của hệ thống chatbot tư vấn bán hàng nội thất}
\label{fig:usecase-overview}
\end{figure}
```

### Sử dụng SVG (cần package svg)
```latex
% Trong preamble
\usepackage{svg}

% Trong document
\begin{figure}[H]
\centering
\includesvg[width=0.9\textwidth]{diagrams/usecase-tong-quat}
\caption{Biểu đồ use case tổng quát của hệ thống chatbot tư vấn bán hàng nội thất}
\label{fig:usecase-overview}
\end{figure}
```

## Labels LaTeX đề xuất

```latex
\label{fig:usecase-overview}              % usecase-tong-quat.puml
\label{fig:usecase-consultation}          % usecase-tu-van-san-pham.puml
\label{fig:usecase-chatbot-kb}            % usecase-quan-ly-chatbot-kb.puml
\label{fig:usecase-price-reference}       % usecase-tham-chieu-gia.puml
\label{fig:usecase-conversation-purchase} % usecase-quan-ly-hoi-thoai-yeu-cau.puml
```

## Ghi chú

- Tất cả file đều sử dụng tiếng Việt cho actor và use case
- Các biểu đồ phân rá chỉ chứa chức năng đã được triển khai trong source code
- Chức năng "So sánh sản phẩm" không có trong diagram vì chưa được triển khai đầy đủ
