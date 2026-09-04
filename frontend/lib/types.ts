export interface Paper {
  id: string;
  title: string | null;
  authors: string[] | null;
  abstract: string | null;
  doi: string | null;
  journal: string | null;
  year: number | null;
  tags: string[] | null;
  filename: string | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface Figure {
  id: string;
  paper_id: string;
  figure_number: number | null;
  image_path: string;
  caption: string | null;
  bbox: number[] | null;
  type: string | null;
  page: number | null;
  created_at: string | null;
}

export interface Job {
  id: string;
  paper_id: string | null;
  job_type: string;
  status: string;
  progress: number;
  error: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Article {
  id: string;
  paper_id: string | null;
  title: string | null;
  summary: string | null;
  content: string | null;
  html: string | null;
  style: string | null;
  skill: string | null;
  images: string[] | null;
  references: string[] | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface PublishRecord {
  id: string;
  article_id: string | null;
  platform: string;
  status: string;
  external_id: string | null;
  error: string | null;
  created_at: string | null;
  published_at: string | null;
}

export interface Health {
  status: string;
  version: string;
  auth_enabled: boolean;
  llm_mode: string;
  mineru_mode: string;
  yolo_mode: string;
  wechat_mode: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
