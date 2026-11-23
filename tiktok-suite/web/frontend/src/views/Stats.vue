<template>
  <div v-loading="loading">
    <!-- 顶部卡片 -->
    <el-row :gutter="12" class="cards">
      <el-col :span="8">
        <el-card shadow="hover"><el-statistic title="总线索" :value="ov.lead_total ?? 0" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover"><el-statistic title="今日动作" :value="todayActions" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="被拦截数" :value="ov.blocked_count ?? 0" value-style="color: #f56c6c" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="12">
      <el-col :span="8"><el-card shadow="never"><div ref="pieEl" class="chart"></div></el-card></el-col>
      <el-col :span="16"><el-card shadow="never"><div ref="barEl" class="chart"></div></el-card></el-col>
    </el-row>
    <el-row :gutter="12" style="margin-top: 12px">
      <el-col :span="8"><el-card shadow="never"><div ref="funnelEl" class="chart"></div></el-card></el-col>
      <el-col :span="16"><el-card shadow="never"><div ref="lineEl" class="chart"></div></el-card></el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import dayjs from 'dayjs';
import * as echarts from 'echarts';
import http from '../api';
import { LEAD_STATUS, statusLabel } from '../utils/constants';

const loading = ref(false);
const ov = ref({});
const pieEl = ref(null);
const barEl = ref(null);
const funnelEl = ref(null);
const lineEl = ref(null);
const charts = [];

// 今日动作数：daily_actions 中日期为今天的三项之和
const todayActions = computed(() => {
  const today = dayjs().format('YYYY-MM-DD');
  const d = (ov.value.daily_actions || []).find((x) => x.date === today);
  return d ? (d.reply || 0) + (d.follow || 0) + (d.dm || 0) : 0;
});

function makeChart(el, option) {
  const c = echarts.init(el);
  c.setOption(option);
  charts.push(c);
}

async function load() {
  loading.value = true;
  try {
    ov.value = await http.get('/stats/overview');
    await nextTick();

    // 状态分布饼图
    const byStatus = ov.value.by_status || {};
    makeChart(pieEl.value, {
      title: { text: '状态分布', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: Object.entries(byStatus).map(([k, v]) => ({ name: statusLabel(LEAD_STATUS, k), value: v })),
      }],
    });

    // 语言 / 国家 bar
    const langs = Object.entries(ov.value.by_lang || {});
    const regs = Object.entries(ov.value.by_region || {});
    makeChart(barEl.value, {
      title: [
        { text: '语言分布', left: '25%', top: 8, textAlign: 'center', textStyle: { fontSize: 14 } },
        { text: '国家分布', left: '75%', top: 8, textAlign: 'center', textStyle: { fontSize: 14 } },
      ],
      tooltip: {},
      grid: [
        { left: '6%', right: '52%', top: 50, bottom: 30 },
        { left: '54%', right: '6%', top: 50, bottom: 30 },
      ],
      xAxis: [
        { type: 'category', data: langs.map(([k]) => k), axisLabel: { rotate: langs.length > 8 ? 40 : 0 } },
        { type: 'category', gridIndex: 1, data: regs.map(([k]) => k), axisLabel: { rotate: regs.length > 8 ? 40 : 0 } },
      ],
      yAxis: [{ type: 'value' }, { type: 'value', gridIndex: 1 }],
      series: [
        { type: 'bar', data: langs.map(([, v]) => v), itemStyle: { color: '#409eff' } },
        { type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: regs.map(([, v]) => v), itemStyle: { color: '#67c23a' } },
      ],
    });

    // 漏斗 new → replied → followed → qualified
    const f = ov.value.funnel || {};
    makeChart(funnelEl.value, {
      title: { text: '转化漏斗', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'item' },
      series: [{
        type: 'funnel', left: '10%', width: '80%',
        data: [
          { name: '新线索', value: f.new ?? 0 },
          { name: '已回复', value: f.replied ?? 0 },
          { name: '已关注', value: f.followed ?? 0 },
          { name: '高意向', value: f.qualified ?? 0 },
        ],
      }],
    });

    // 近 14 日动作折线
    const days = (ov.value.daily_actions || []).slice(-14);
    makeChart(lineEl.value, {
      title: { text: '近 14 日动作', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 40, right: 20, top: 40, bottom: 40 },
      xAxis: { type: 'category', data: days.map((d) => d.date?.slice(5)) },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        { name: '回复', type: 'line', smooth: true, data: days.map((d) => d.reply || 0) },
        { name: '关注', type: 'line', smooth: true, data: days.map((d) => d.follow || 0) },
        { name: '私信', type: 'line', smooth: true, data: days.map((d) => d.dm || 0) },
      ],
    });
  } finally {
    loading.value = false;
  }
}

function onResize() {
  charts.forEach((c) => c.resize());
}

onMounted(() => {
  load();
  window.addEventListener('resize', onResize);
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize);
  charts.forEach((c) => c.dispose());
});
</script>

<style scoped>
.cards { margin-bottom: 12px; }
.chart { height: 300px; }
</style>
