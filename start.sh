# docker build --build-arg make_jobs=8 -t my-python .
# docker run -it my-python

# Build for x86_64 architecture
docker build --platform linux/amd64 --build-arg make_jobs=8 -t my-python-x86 .

# Run the container
docker run --platform linux/amd64 -it my-python-x86

