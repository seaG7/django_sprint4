from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    ListView, DetailView, CreateView, DeleteView, UpdateView
)
from django.utils import timezone
from .models import Post, Category, Comment
from .forms import PostForm, CommentForm
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count


def get_comment_count_queryset(posts):
    return posts.annotate(comment_count=Count('comment'))


def paginate_posts(posts, request, per_page=10):
    paginator = Paginator(posts, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


class PostsListsMixin:
    model = Post
    paginate_by = 10

    def get_queryset(self):
        now = timezone.now()
        posts = Post.objects.filter(
            pub_date__lte=now,
            is_published=True,
            category__is_published=True
        )
        return get_comment_count_queryset(posts).order_by('-pub_date')


class PostsListView(PostsListsMixin, ListView):
    template_name = 'blog/index.html'


class CategoryListView(PostsListsMixin, ListView):
    template_name = 'blog/category.html'
    context_object_name = 'page_obj'

    def get_queryset(self):
        category_slug = self.kwargs['slug']
        category = get_object_or_404(
            Category, slug=category_slug, is_published=True)
        return get_comment_count_queryset(
            super().get_queryset().
            filter(category=category)).order_by('-pub_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category'] = get_object_or_404(
            Category, slug=self.kwargs['slug'], is_published=True)
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    context_object_name = 'post'

    def get_object(self, queryset=None):
        post = get_object_or_404(Post, pk=self.kwargs['post_id'])
        now = timezone.now()

        if self.request.user != post.author:
            if (
                post.pub_date > now
                or not post.is_published
                or not post.category.is_published
            ):
                raise Http404("Публикация не найдена или недоступна.")
        return post

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.object.comment_set.all()
        if self.request.user.is_authenticated:
            context['form'] = CommentForm()
        return context


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', kwargs={
            'username': self.request.user.username})


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('blog:post_detail', post_id=self.kwargs['post_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if form.instance.author != self.request.user:
            return redirect('blog:post_detail', post_id=self.kwargs['post_id'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile',
                            kwargs={'username': self.request.user.username})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'

    def get_object(self, queryset=None):
        post_id = self.kwargs.get('post_id')
        post = get_object_or_404(Post, pk=post_id)
        if post.author != self.request.user and not self.request.user.is_staff:
            raise Http404("Удаление запрещено")
        return post

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.get_object())
        return context

    def get_success_url(self):
        return reverse('blog:profile', kwargs={
            'username': self.request.user.username})


class UserDetailView(DetailView):
    model = get_user_model()
    template_name = 'blog/profile.html'
    context_object_name = 'profile'

    def get_object(self, queryset=None):
        return get_object_or_404(get_user_model(),
                                 username=self.kwargs['username'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        if self.request.user == self.object:
            posts = Post.objects.filter(author=self.object)
        else:
            posts = Post.objects.filter(
                author=self.object,
                is_published=True,
                pub_date__lte=now,
                category__is_published=True
            )

        posts = get_comment_count_queryset(posts).order_by('-pub_date')
        context['page_obj'] = paginate_posts(posts, self.request)
        return context


class UserUpdateView(LoginRequiredMixin, UpdateView):
    model = get_user_model()
    template_name = 'blog/user.html'
    context_object_name = 'profile'
    fields = ['username', 'first_name', 'last_name', 'email']

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile',
                            kwargs={'username': self.object.username})


class CommentMixin:
    model = Comment
    form_class = CommentForm
    template_name = 'blog/comment.html'

    def get_post(self):
        return get_object_or_404(Post, id=self.kwargs['post_id'])

    def get_success_url(self):
        return reverse('blog:post_detail',
                            kwargs={'post_id': self.get_post().id})


class EditCommentMixin(CommentMixin):
    def get_object(self, queryset=None):
        comment_id = self.kwargs.get('comment_id')
        comment = get_object_or_404(Comment, pk=comment_id)
        if comment.author != self.request.user:
            raise Http404("Действие запрещено")
        return comment


class CommentCreateView(LoginRequiredMixin, CommentMixin, CreateView):
    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.get_post()
        return super().form_valid(form)


class CommentUpdateView(LoginRequiredMixin, EditCommentMixin, UpdateView):
    pass


class CommentDeleteView(LoginRequiredMixin, EditCommentMixin, DeleteView):
    pass


class CommentListView(ListView):
    model = Comment
    template_name = 'blog/comment.html'
    form_class = CommentForm