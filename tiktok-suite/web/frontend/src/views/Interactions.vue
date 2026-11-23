<template>
  <div>
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="动作类型">
          <el-select v-model="filters.action_type" placeholder="全部" clearable style="width: 130px" @change="load">
            <el-option v-for="t in ACTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 130px" @change="load">
            <el-option v-for="s in INTERACTION_STATUS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="'Search'" @click="load">查询</el-button>
          <el-button :icon="'Refresh'" @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="rows" v-loading="loading">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="用户" width="160">
          <template #default="{ row }">@{{ row.username || ('#' + row.lead_id) }}</template>
        </el-table-column>
        <el-table-column label="动作" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(ACTION_TYPES, row.action_type)">{{ statusLabel(ACTION_TYPES, row.action_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="内容摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.content || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(INTERACTION_STATUS, row.status)">{{ statusLabel(INTERACTION_STATUS, row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="平台返回" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.platform_msg || '-' }}</template>
        </el-table-column>
        <template #empty><el-empty description="暂无互动记录" /></template>
      </el-table>
      <div class="pager">
        <span class="total">共 {{ total }} 条</span>
        <el-pagination background layout="prev, pager, next" :total="total" :page-size="pageSize"
          :current-page="page" @current-change="onPage" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import dayjs from 'dayjs';
import http from '../api';
import { ACTION_TYPES, INTERACTION_STATUS, statusLabel, statusTag } from '../utils/constants';

const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const loading = ref(false);
const filters = reactive({ action_type: '', status: '' });

const fmtTime = (t) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-');

async function load() {
  loading.value = true;
  try {
    const data = await http.get('/interactions', {
      params: { ...filters, limit: pageSize, offset: (page.value - 1) * pageSize },
    });
    rows.value = data.items || [];
    total.value = data.total ?? rows.value.length;
  } finally {
    loading.value = false;
  }
}

function reset() {
  Object.assign(filters, { action_type: '', status: '' });
  page.value = 1;
  load();
}

function onPage(p) {
  page.value = p;
  load();
}

onMounted(load);
</script>

<style scoped>
.filter-card { margin-bottom: 12px; }
.pager { margin-top: 12px; display: flex; align-items: center; gap: 16px; justify-content: flex-end; }
.total { color: #909399; font-size: 13px; }
</style>
