// Pagination

export interface PaginationRequest {
  page: number;
  size: number;
}

export interface PaginationResponse<T> {
  content: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}