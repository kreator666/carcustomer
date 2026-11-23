<template>
  <div>
    <el-card shadow="never">
      <div class="toolbar">
        <el-button type="primary" :icon="'Plus'" @click="addVisible = true">添加视频</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column label="视频链接" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link type="primary" :href="row.url" target="_blank">{{ row.url }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
        <el-table-column prop="author_username" label="作者" width="140" show-overflow-tooltip />
        <el-table-column label="监控" width="90">
          <template #default="{ row }">
            <el-switch :model-value="!!row.monitor" :loading="row._switching"
              @change="(v) => toggleMonitor(row, v)" />
          </template>
        </el-table-column>
        <el-table-column label="最近扫描" width="170">
          <template #default="{ row }">{{ fmtTime(row.last_scanned_at) }}</template>
        </el-table-column>
        <el-table-column prop="lead_count" label="线索数" width="90" sortable />
        <template #empty><el-empty description="暂无视频" /></template>
      </el-table>
    </el-card>

    <!-- 添加视频对话框 -->
    <el-dialog v-model="addVisible" title="添加视频" width="480px">
      <el-input v-model="newUrl" placeholder="粘贴 TikTok 视频 URL，如 https://www.tiktok.com/@user/video/..." />
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="addVideo" :loading="adding">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import dayjs from 'dayjs';
import { ElMessage } from 'element-plus';
import http from '../api';

const rows = ref([]);
const loading = ref(false);
const addVisible = ref(false);
const newUrl = ref('');
const adding = ref(false);

const fmtTime = (t) => (t ? dayjs(t).format('MM-DD HH:mm') : '-');

async function load() {
  loading.value = true;
  try {
    const data = await http.get('/videos');
    rows.value = (data.items || []).map((r) => ({ ...r, _switching: false }));
  } finally {
    loading.value = false;
  }
}

async function addVideo() {
  if (!newUrl.value.trim()) return;
  adding.value = true;
  try {
    await http.post('/videos', { url: newUrl.value.trim() });
    ElMessage.success('已添加');
    addVisible.value = false;
    newUrl.value = '';
    load();
  } finally {
    adding.value = false;
  }
}

async function toggleMonitor(row, val) {
  row._switching = true;
  try {
    const updated = await http.patch(`/videos/${row.id}`, { monitor: val ? 1 : 0 });
    row.monitor = updated.monitor;
  } finally {
    row._switching = false;
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar { margin-bottom: 12px; }
</style>
