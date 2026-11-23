// 共享常量：状态、类型与标签颜色映射
export const LEAD_STATUS = [
  { value: 'new', label: '新线索', tag: 'info' },
  { value: 'replied', label: '已回复', tag: 'primary' },
  { value: 'followed', label: '已关注', tag: 'warning' },
  { value: 'contacted', label: '已联系', tag: 'success' },
  { value: 'qualified', label: '高意向', tag: 'danger' },
  { value: 'dead', label: '无效', tag: 'info' },
];

export const ACTION_TYPES = [
  { value: 'reply', label: '回复', tag: 'primary' },
  { value: 'follow', label: '关注', tag: 'warning' },
  { value: 'dm', label: '私信', tag: 'success' },
];

export const INTERACTION_STATUS = [
  { value: 'success', label: '成功', tag: 'success' },
  { value: 'blocked', label: '被拦截', tag: 'danger' },
  { value: 'error', label: '失败', tag: 'warning' },
];

export const LANGS = ['en', 'zh', 'es', 'ru', 'it', 'fr', 'ar', 'pt', 'de', 'other'];

export const statusLabel = (list, v) => (list.find((s) => s.value === v) || {}).label || v || '-';
export const statusTag = (list, v) => (list.find((s) => s.value === v) || {}).tag || 'info';

// 意向分色阶：分数越高越红
export function scoreType(score) {
  if (score >= 80) return 'danger';
  if (score >= 60) return 'warning';
  if (score >= 40) return 'primary';
  return 'info';
}
