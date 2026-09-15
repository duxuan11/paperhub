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
  author: string | null;
  theme: string | null;
  cover_image: string | null;
  images: string[] | null;
  references: string[] | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

/** 单个元素的 inline style：CSS 属性 -> 值 */
export interface WechatThemeStyle {
  [prop: string]: string;
}

/** 主题配色设计变量 */
export interface WechatThemeColors {
  primary: string;
  secondary: string;
  text: string;
  muted: string;
  background: string;
  border: string;
}

/** 主题字体排版设计变量 */
export interface WechatThemeTypography {
  fontFamily?: string | null;
  bodySize: string;
  bodyLineHeight: string;
  heading1Size: string;
  heading2Size: string;
  heading3Size: string;
  captionSize: string;
}

/** 主题设计变量：配色 + 字体排版 + 组件级 CSS 覆盖 */
export interface WechatThemeConfig {
  colors: WechatThemeColors;
  typography: WechatThemeTypography;
  components: Record<string, WechatThemeStyle>;
}

/** 公众号主题（由后端 /wechat/themes 提供，前端据此实时渲染预览） */
export interface WechatTheme {
  id: string;
  name: string;
  description?: string;
  /** 设计变量（编辑用） */
  config?: WechatThemeConfig;
  /** 编译后的元素样式（渲染用，与后端一致） */
  styles: Record<string, WechatThemeStyle>;
  options?: Record<string, unknown>;
  is_builtin?: boolean;
  is_default?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
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

/** AI 分析可选的 Skill（来自后端 skills/ 目录） */
export interface AnalysisSkill {
  name: string;
  description: string;
  tools: string[];
  prompt: string;
}

/** 论文级 AI 分析配置 */
export interface AIAnalysisConfig {
  paper_id: string;
  enabled: boolean;
  model: string;
  selected_skills: string[];
  custom_prompt: string;
  default_model: string;
  default_skills: string[];
  available_skills: AnalysisSkill[];
  updated_at?: string | null;
}

/** 每个 Skill 一条的结构化分析结果 */
export interface AIAnalysisResult {
  paper_id: string;
  skill: string;
  content: string;
  model: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** GET /papers/{id}/ai-analysis 的响应 */
export interface AIAnalysisPayload {
  paper_id: string;
  parsed: boolean;
  config: AIAnalysisConfig;
  results: AIAnalysisResult[];
}
