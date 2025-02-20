-- Enable the pgvector extension
create extension if not exists vector;

-- Create the documentation chunks table
create table if not exists documentation (
    id bigint generated always as identity primary key,
    title text not null,
    summary text not null,
    content text not null,
    url text not null,
    base_url text not null,
    chunk_index smallint not null,
    embedding vector(768) not null,  -- nomic-ai/nomic-embed-text-v1.5 embeddings are 768 dimensions
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(url, chunk_index)
);

-- Create an index for better vector similarity search performance
create index on documentation using ivfflat (embedding vector_cosine_ops);

-- Create a function to search for documentation chunks
create or replace function match_documentation (
  query_embedding vector(768),
  match_count int default 3
) returns table (
  id bigint,
  title text,
  summary text,
  content text,
  url text,
  base_url text,
  chunk_index smallint,
  created_at timestamp with time zone,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    title,
    summary,
    content,
    url,
    base_url,
    chunk_index,
    created_at,
    1 - (documentation.embedding <=> query_embedding) as similarity
  from documentation
  order by documentation.embedding <=> query_embedding
  limit match_count;
end;
$$;