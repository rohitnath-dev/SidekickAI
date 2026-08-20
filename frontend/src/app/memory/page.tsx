'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  BrainCircuit, 
  Search, 
  Plus, 
  Trash2, 
  Sparkles, 
  User, 
  FolderGit, 
  Bookmark, 
  Loader2,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import SidebarLayout from '@/components/layout';
import { apiClient } from '@/lib/api-client';

export default function MemoryPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  
  // Manual Extraction states
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractText, setExtractText] = useState('');
  const [extractResult, setExtractResult] = useState<string | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);

  // Fetch memories list
  const { data: memories, isLoading: isMemoriesLoading } = useQuery({
    queryKey: ['memories', searchQuery, categoryFilter],
    queryFn: async () => {
      let endpoint = '/memory';
      const params: any = {};
      
      if (searchQuery) {
        endpoint = '/memory/search';
        params.q = searchQuery;
      }
      
      if (categoryFilter !== 'all' && !searchQuery) {
        params.category = categoryFilter;
      }

      const response = await apiClient.get(endpoint, { params });
      return response.data;
    },
  });

  // Extract memory mutation
  const extractMutation = useMutation({
    mutationFn: async () => {
      setIsExtracting(true);
      setExtractResult(null);
      setExtractError(null);
      const response = await apiClient.post('/memory/extract', {
        message_content: extractText
      });
      return response.data;
    },
    onSuccess: (data) => {
      setExtractResult(`Successfully added ${data.length} new memories.`);
      setExtractText('');
      queryClient.invalidateQueries({ queryKey: ['memories'] });
      setTimeout(() => setExtractResult(null), 4000);
    },
    onError: (err: any) => {
      console.error(err);
      setExtractError(err.response?.data?.detail || 'Unable to add this to memory. Please try again.');
    },
    onSettled: () => {
      setIsExtracting(false);
    }
  });

  // Delete memory mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.delete(`/memory/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memories'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || 'Failed to delete memory item.');
    }
  });

  const categories = ['all', 'personal', 'project', 'schedule', 'contact', 'other'];

  return (
    <SidebarLayout>
      <div className="p-6 md:p-8 space-y-8 max-w-6xl mx-auto h-full overflow-y-auto">
        
        {/* Header */}
        <div className="border-b border-zinc-900 pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-50">Long-term Memory</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Browse, search, and manage information Sidekick remembers about you.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Columns: Search & Memories List */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Search and Filters */}
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-zinc-500" />
                <input
                  type="text"
                  placeholder="Search your memories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-850 rounded-lg pl-9 pr-4 py-2 text-xs text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-700 transition-all"
                />
              </div>

              {!searchQuery && (
                <div className="flex items-center gap-2">
                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="bg-zinc-900 border border-zinc-850 rounded-lg px-2.5 py-2 text-xs text-zinc-350 focus:text-zinc-100 outline-none cursor-pointer"
                  >
                    {categories.map((cat) => (
                      <option key={cat} value={cat} className="capitalize">
                        {cat === 'all' ? 'All Categories' : cat}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* List */}
            <div className="space-y-4">
              {isMemoriesLoading ? (
                <div className="py-12 flex justify-center text-zinc-500">
                  <Loader2 className="w-6 h-6 animate-spin text-zinc-400" />
                </div>
              ) : memories && memories.length > 0 ? (
                <div className="grid grid-cols-1 gap-4">
                  {memories.map((item: any) => (
                    <div 
                      key={item.id}
                      className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-5 space-y-4 relative group"
                    >
                      <button
                        onClick={() => deleteMutation.mutate(item.id)}
                        className="absolute top-4 right-4 p-1 text-zinc-650 hover:text-rose-400 rounded-lg hover:bg-rose-950/20 border border-transparent hover:border-rose-900/30 transition-all cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>

                      <p className="text-xs text-zinc-200 leading-relaxed font-normal pr-6">
                        {item.content}
                      </p>

                      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-900/50 text-[10px] text-zinc-450 font-medium">
                        <span className="bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded text-zinc-350 capitalize">
                          {item.category}
                        </span>

                        {item.related_person && (
                          <span className="flex items-center gap-1 bg-zinc-900/40 border border-zinc-900 px-2 py-0.5 rounded text-zinc-400">
                            <User className="w-3 h-3 text-zinc-550" />
                            {item.related_person}
                          </span>
                        )}

                        {item.related_project && (
                          <span className="flex items-center gap-1 bg-zinc-900/40 border border-zinc-900 px-2 py-0.5 rounded text-zinc-400">
                            <FolderGit className="w-3 h-3 text-zinc-550" />
                            {item.related_project}
                          </span>
                        )}

                        {item.retention_value && (
                          <span className="flex items-center gap-1 bg-zinc-900/40 border border-zinc-900 px-2 py-0.5 rounded text-zinc-400">
                            <Bookmark className="w-3 h-3 text-zinc-550" />
                            {item.retention_value}
                          </span>
                        )}

                        {item.confidence !== undefined && (
                          <span className="ml-auto text-[9px] font-mono text-zinc-550">
                            Confidence: {Math.round(item.confidence * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-12 text-center border border-dashed border-zinc-850 rounded-xl p-6">
                  <BrainCircuit className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
                  <p className="text-xs text-zinc-400 font-semibold">No memories recorded yet</p>
                  <p className="text-[10px] text-zinc-500 mt-0.5">
                    Add something important to your memory, or let Sidekick remember useful information from your conversations.
                  </p>
                </div>
              )}
            </div>

          </div>

          {/* Right Column: Add to Memory Panel */}
          <div className="space-y-6">
            <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-6 space-y-6">
              <div className="flex items-center gap-2 border-b border-zinc-900 pb-3">
                <Sparkles className="w-4 h-4 text-zinc-400" />
                <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Add to Memory</h2>
              </div>

              {extractResult && (
                <div className="flex items-start gap-2.5 rounded-lg border border-emerald-900/30 bg-emerald-950/20 p-4 text-xs text-emerald-400">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500 mt-0.5" />
                  <span>{extractResult}</span>
                </div>
              )}

              {extractError && (
                <div className="flex items-start gap-2.5 rounded-lg border border-red-900/30 bg-red-950/20 p-4 text-xs text-red-400">
                  <AlertCircle className="h-4 w-4 shrink-0 text-red-500 mt-0.5" />
                  <span>{extractError}</span>
                </div>
              )}

              <div className="space-y-4">
                <p className="text-[11px] text-zinc-450 leading-relaxed font-normal">
                  Save useful information for future conversations. Sidekick will identify important, lasting facts and add them to your long-term memory.
                </p>

                <textarea
                  placeholder="Paste something you want Sidekick to remember..."
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  rows={8}
                  className="w-full bg-zinc-950 border border-zinc-850 rounded-lg p-3 text-xs text-zinc-200 placeholder-zinc-600 outline-none focus:border-zinc-700 transition-all resize-none leading-relaxed"
                />

                <button
                  onClick={() => extractMutation.mutate()}
                  disabled={isExtracting || !extractText}
                  className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 text-xs font-semibold text-zinc-950 transition-all cursor-pointer disabled:opacity-50"
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Adding to Memory...
                    </>
                  ) : (
                    <>
                      <Plus className="w-3.5 h-3.5" />
                      Add to Memory
                    </>
                  )}
                </button>
              </div>

            </div>
          </div>

        </div>

      </div>
    </SidebarLayout>
  );
}