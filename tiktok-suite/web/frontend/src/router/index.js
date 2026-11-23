import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/', redirect: '/leads' },
  { path: '/leads', name: 'leads', component: () => import('../views/Leads.vue'), meta: { title: '线索列表' } },
  { path: '/interactions', name: 'interactions', component: () => import('../views/Interactions.vue'), meta: { title: '互动日志' } },
  { path: '/videos', name: 'videos', component: () => import('../views/Videos.vue'), meta: { title: '视频管理' } },
  { path: '/stats', name: 'stats', component: () => import('../views/Stats.vue'), meta: { title: '数据统计' } },
  { path: '/templates', name: 'templates', component: () => import('../views/Templates.vue'), meta: { title: '话术模板' } },
  { path: '/settings', name: 'settings', component: () => import('../views/Settings.vue'), meta: { title: '设置' } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
