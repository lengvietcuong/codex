-- Create the documentation table
create table if not exists documentation (
    id bigint generated always as identity primary key,
    title text not null,
    summary text not null,
    content text not null,
    url text not null,
    base_url text not null,
    chunk_index smallint not null,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(url, chunk_index)
);