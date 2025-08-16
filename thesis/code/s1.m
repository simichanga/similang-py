function [varargout]=drawCells(H,h,tuples,varargin)

[~,d]=size(H);

if nargin<4
    opt={'Alpha',0.4,'Color','b'};
else
    opt={varargin{:}{:}};
end

tmp_all=[];
for i=1:size(tuples,2)
    tuple=tuples(:,i);
    ii=find(tuple~=0.5); % discard the indices corresponding to hyperplanes which are covered on both sides (useful for merged tuples)    
    tmp=Polyhedron(H(ii,:).*repmat(2*tuple(ii)-1,1,d),h(ii).*(2*tuple(ii)-1));
    tmp_all=[tmp_all tmp];
end

switch nargout
    case 1
        varargout{1}=tmp_all;
    case 0
        a=axis(gca);
        hold on
        plot(tmp_all,opt{:})
        axis(a);
    case 2
        varargout{1}=tmp_all;
        a=axis(gca);
        hold on
        varargout{2}=plot(tmp_all,opt{:});
        axis(a);
    otherwise
        error 'not an accepted number of outputs'
end
